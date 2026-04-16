import axios from 'axios';
import SparkMD5 from 'spark-md5';
import appConfig from '@/config/appConfig.json';

export function buildBackendUrl(path) {
    if (!path) {
        return '';
    }
    if (path.startsWith('http://') || path.startsWith('https://')) {
        return path;
    }
    return `${appConfig.backendUrl}${path}`;
}

async function computeFileHash(file) {
    if (!(file instanceof File) && !(file instanceof Blob)) {
        return null;
    }

    const chunkSize = 2 * 1024 * 1024;
    const spark = new SparkMD5.ArrayBuffer();
    let offset = 0;

    while (offset < file.size) {
        const chunk = file.slice(offset, offset + chunkSize);
        const buffer = await chunk.arrayBuffer();
        spark.append(buffer);
        offset += chunkSize;
    }

    return spark.end();
}

async function requestUpload(file, kind) {
    const fileHash = await computeFileHash(file);
    const fileResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/draft`,
        {
            filename: file.name,
            contentType: file.type || 'application/octet-stream',
            size: file.size,
            kind,
            fileHash,
        },
    );

    const fileRecord = fileResponse.data;
    const { fileId, uploadStatus, parseStatus } = fileRecord;
    if (kind === 'book') {
        const sameHash = Boolean(fileHash && fileRecord.fileHash && fileHash === fileRecord.fileHash);
        const sameName = fileRecord.originalFilename === file.name;
        const looksLikeExistingDraft = !(uploadStatus === 'init' && parseStatus === 'not_started');
        if (looksLikeExistingDraft && !sameHash && !sameName) {
            throw new Error('当前已有一本待创建的书籍正在处理中，请先完成创建或删除后再上传新的正文文件。');
        }
    }
    if (uploadStatus === 'uploaded') {
        return {
            fileId,
            alreadyUploaded: true,
            parseStatus,
        };
    }

    const uploadUrlResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/${fileId}/upload-session`,
    );

    const { objectKey, uploadUrl, headers, mockUpload } = uploadUrlResponse.data;
    if (!mockUpload && (!uploadUrl || !objectKey)) {
        throw new Error('后端未返回有效的上传链接');
    }

    const contentType = file.type || headers?.['Content-Type'] || 'application/octet-stream';
    let etag = null;

    if (!mockUpload) {
        const uploadResponse = await fetch(uploadUrl, {
            method: 'PUT',
            headers: {
                ...(headers || {}),
                'Content-Type': contentType,
            },
            body: file,
        });

        if (!uploadResponse.ok) {
            throw new Error(`上传文件到对象存储失败: ${uploadResponse.status}`);
        }
        etag = uploadResponse.headers.get('etag');
    }

    const completeResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/${fileId}/complete`,
        {
            etag,
        },
    );

    return completeResponse.data;
}

export async function uploadFileToStorage(file, kind) {
    const result = await requestUpload(file, kind);
    return result.fileId;
}

export async function fetchParseResult(fileId) {
    const response = await axios.get(`${appConfig.backendUrl}/api/files/${fileId}/parse`);
    return response.data;
}

export async function waitForParseResult(fileId, options = {}) {
    const {
        timeoutMs = 180000,
        intervalMs = 1000,
    } = options;
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
        const result = await fetchParseResult(fileId);
        if (result.parseStatus === 'done') {
            return result;
        }
        await new Promise((resolve) => {
            window.setTimeout(resolve, intervalMs);
        });
    }

    return {
        parseStatus: 'timeout',
    };
}

export async function uploadBookFileAndWaitForParse(file, options = {}) {
    const uploadResult = await requestUpload(file, 'book');
    if (uploadResult.parseStatus === 'done') {
        const parseResult = await fetchParseResult(uploadResult.fileId);
        return {
            ...uploadResult,
            parseResult,
        };
    }
    const parseResult = await waitForParseResult(uploadResult.fileId, options);
    return {
        ...uploadResult,
        parseResult,
    };
}

export async function fetchDownloadUrl(fileId) {
    const response = await axios.get(`${appConfig.backendUrl}/api/files/${fileId}/download`);
    return response.data.downloadUrl;
}

export function extractFileIdFromPath(path) {
    if (!path) {
        return null;
    }
    const match = String(path).match(/\/api\/files\/(\d+)\/download(?:\?.*)?$/);
    if (!match) {
        return null;
    }
    return Number(match[1]);
}

export async function resolveFileAccessUrl(pathOrFileId) {
    if (pathOrFileId === null || pathOrFileId === undefined || pathOrFileId === '') {
        return '';
    }
    if (typeof pathOrFileId === 'number') {
        return fetchDownloadUrl(pathOrFileId);
    }
    if (typeof pathOrFileId === 'string' && (pathOrFileId.startsWith('http://') || pathOrFileId.startsWith('https://'))) {
        return pathOrFileId;
    }
    const fileId = extractFileIdFromPath(pathOrFileId);
    if (fileId) {
        return fetchDownloadUrl(fileId);
    }
    return buildBackendUrl(pathOrFileId);
}

export async function downloadByFileId(fileId) {
    const downloadUrl = await fetchDownloadUrl(fileId);
    if (!downloadUrl) {
        throw new Error('后端未返回可用的下载链接');
    }
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.rel = 'noopener noreferrer';
    link.target = '_self';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
