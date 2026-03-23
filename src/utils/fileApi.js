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
    const uploadUrlResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/upload-url`,
        {
            filename: file.name,
            contentType: file.type || 'application/octet-stream',
            size: file.size,
            kind,
            fileHash,
        },
    );

    const { fileId, objectKey, uploadUrl, headers } = uploadUrlResponse.data;
    if (fileId && !uploadUrl) {
        return {
            fileId,
            alreadyUploaded: true,
            parseStatus: kind === 'book' ? 'unknown' : 'skipped',
        };
    }
    if (!uploadUrl || !objectKey) {
        throw new Error('后端未返回有效的上传链接');
    }

    const contentType = file.type || headers?.['Content-Type'] || 'application/octet-stream';

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

    const completeResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/upload-complete`,
        {
            objectKey,
            originalFilename: file.name,
            contentType,
            size: file.size,
            kind,
            etag: uploadResponse.headers.get('etag'),
        },
    );

    return completeResponse.data;
}

export async function uploadFileToStorage(file, kind) {
    const result = await requestUpload(file, kind);
    return result.fileId;
}

export async function fetchParseResult(fileId) {
    const response = await axios.get(`${appConfig.backendUrl}/api/files/${fileId}/parse-result`);
    return response.data;
}

export async function waitForParseResult(fileId, options = {}) {
    const {
        timeoutMs = 30000,
        intervalMs = 1000,
    } = options;
    const start = Date.now();

    while (Date.now() - start < timeoutMs) {
        const result = await fetchParseResult(fileId);
        if (['done', 'failed', 'dispatch_failed', 'missing'].includes(result.status)) {
            return result;
        }
        await new Promise((resolve) => {
            window.setTimeout(resolve, intervalMs);
        });
    }

    return {
        status: 'timeout',
    };
}

export async function uploadBookFileAndWaitForParse(file, options = {}) {
    const uploadResult = await requestUpload(file, 'book');
    const parseResult = await waitForParseResult(uploadResult.fileId, options);
    return {
        ...uploadResult,
        parseResult,
    };
}

export async function fetchDownloadUrl(fileId) {
    const response = await axios.get(`${appConfig.backendUrl}/api/files/${fileId}/download-url`);
    return response.data.downloadUrl;
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
