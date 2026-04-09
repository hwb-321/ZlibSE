#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import socket
import struct
import sys
from dataclasses import dataclass


LINKTYPE_ETHERNET = 1
LINKTYPE_LINUX_SLL = 113
LINKTYPE_LINUX_SLL2 = 276
ETHERTYPE_IPV4 = 0x0800


@dataclass
class Stats:
    packets: int = 0
    ip_bytes: int = 0
    tcp_header_bytes: int = 0
    tcp_payload_bytes: int = 0

    def add(self, *, ip_total_length: int, tcp_header_length: int, tcp_payload_length: int) -> None:
        self.packets += 1
        self.ip_bytes += ip_total_length
        self.tcp_header_bytes += tcp_header_length
        self.tcp_payload_bytes += tcp_payload_length


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统计 pcap 中指定 TCP 端口的 TCP/IP 报文字节数。")
    parser.add_argument("pcap", help="pcap 文件路径")
    parser.add_argument("--port", type=int, required=True, help="目标 TCP 端口，例如 8000")
    parser.add_argument("--host", help="可选，限制对端 IP，例如 49.232.49.66")
    return parser.parse_args()


def _read_pcap_global_header(fp) -> tuple[str, int]:
    raw = fp.read(24)
    if len(raw) != 24:
        raise ValueError("pcap 文件头不完整")

    magic = raw[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        endian = "<"
    elif magic == b"\xa1\xb2\xc3\xd4":
        endian = ">"
    else:
        raise ValueError("仅支持 pcap 格式，不支持 pcapng")

    _version_major, _version_minor, _thiszone, _sigfigs, _snaplen, network = struct.unpack(
        f"{endian}HHiiii", raw[4:24]
    )
    return endian, network


def _iter_pcap_packets(fp, endian: str):
    header_fmt = f"{endian}IIII"
    header_size = struct.calcsize(header_fmt)
    while True:
        header = fp.read(header_size)
        if not header:
            return
        if len(header) != header_size:
            raise ValueError("pcap 记录头不完整")
        _ts_sec, _ts_usec, incl_len, _orig_len = struct.unpack(header_fmt, header)
        packet = fp.read(incl_len)
        if len(packet) != incl_len:
            raise ValueError("pcap 数据包内容不完整")
        yield packet


def _extract_ipv4_packet(packet: bytes, linktype: int) -> bytes | None:
    if linktype == LINKTYPE_ETHERNET:
        if len(packet) < 14:
            return None
        ether_type = struct.unpack("!H", packet[12:14])[0]
        if ether_type != ETHERTYPE_IPV4:
            return None
        return packet[14:]

    if linktype == LINKTYPE_LINUX_SLL:
        if len(packet) < 16:
            return None
        protocol = struct.unpack("!H", packet[14:16])[0]
        if protocol != ETHERTYPE_IPV4:
            return None
        return packet[16:]

    if linktype == LINKTYPE_LINUX_SLL2:
        if len(packet) < 20:
            return None
        protocol = struct.unpack("!H", packet[0:2])[0]
        if protocol != ETHERTYPE_IPV4:
            return None
        return packet[20:]

    raise ValueError(f"暂不支持的链路层类型: {linktype}")


def _format_bytes(num: int) -> str:
    if num < 1024:
        return f"{num} B"
    if num < 1024 * 1024:
        return f"{num / 1024:.2f} KiB"
    return f"{num / 1024 / 1024:.2f} MiB"


def main() -> int:
    args = _parse_args()
    peer_host = ipaddress.ip_address(args.host) if args.host else None

    inbound = Stats()
    outbound = Stats()

    with open(args.pcap, "rb") as fp:
        endian, linktype = _read_pcap_global_header(fp)
        for raw_packet in _iter_pcap_packets(fp, endian):
            ip_packet = _extract_ipv4_packet(raw_packet, linktype)
            if not ip_packet or len(ip_packet) < 20:
                continue

            version_ihl = ip_packet[0]
            version = version_ihl >> 4
            if version != 4:
                continue
            ip_header_length = (version_ihl & 0x0F) * 4
            if len(ip_packet) < ip_header_length or ip_header_length < 20:
                continue

            protocol = ip_packet[9]
            if protocol != socket.IPPROTO_TCP:
                continue

            ip_total_length = struct.unpack("!H", ip_packet[2:4])[0]
            if ip_total_length < ip_header_length + 20 or len(ip_packet) < ip_total_length:
                continue

            src_ip = ipaddress.ip_address(ip_packet[12:16])
            dst_ip = ipaddress.ip_address(ip_packet[16:20])
            tcp_segment = ip_packet[ip_header_length:ip_total_length]
            if len(tcp_segment) < 20:
                continue

            src_port, dst_port = struct.unpack("!HH", tcp_segment[:4])
            if src_port != args.port and dst_port != args.port:
                continue

            if peer_host is not None and src_ip != peer_host and dst_ip != peer_host:
                continue

            tcp_header_length = ((tcp_segment[12] >> 4) & 0x0F) * 4
            if tcp_header_length < 20 or len(tcp_segment) < tcp_header_length:
                continue

            tcp_payload_length = len(tcp_segment) - tcp_header_length
            target = inbound if dst_port == args.port else outbound
            target.add(
                ip_total_length=ip_total_length,
                tcp_header_length=tcp_header_length,
                tcp_payload_length=tcp_payload_length,
            )

    total_packets = inbound.packets + outbound.packets
    total_ip_bytes = inbound.ip_bytes + outbound.ip_bytes
    total_tcp_header_bytes = inbound.tcp_header_bytes + outbound.tcp_header_bytes
    total_tcp_payload_bytes = inbound.tcp_payload_bytes + outbound.tcp_payload_bytes

    print("TCP/IP 抓包统计")
    print(f"- 目标端口: {args.port}")
    if args.host:
        print(f"- 目标主机: {args.host}")
    print(f"- 入站报文数: {inbound.packets}")
    print(f"- 出站报文数: {outbound.packets}")
    print(f"- 总报文数: {total_packets}")
    print(f"- 入站 IP 总字节(含 IP+TCP 头+TCP 负载): {inbound.ip_bytes} ({_format_bytes(inbound.ip_bytes)})")
    print(f"- 出站 IP 总字节(含 IP+TCP 头+TCP 负载): {outbound.ip_bytes} ({_format_bytes(outbound.ip_bytes)})")
    print(f"- 总 IP 字节(含 TCP/IP 头): {total_ip_bytes} ({_format_bytes(total_ip_bytes)})")
    print(
        f"- TCP 头总字节(含 ACK 报文的 TCP 头): {total_tcp_header_bytes} ({_format_bytes(total_tcp_header_bytes)})"
    )
    print(f"- TCP 负载总字节: {total_tcp_payload_bytes} ({_format_bytes(total_tcp_payload_bytes)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
