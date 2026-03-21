import axios from 'axios';
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

export async function uploadFileToStorage(file, kind) {
    const uploadUrlResponse = await axios.post(
        `${appConfig.backendUrl}/api/files/upload-url`,
        {
            filename: file.name,
            contentType: file.type || 'application/octet-stream',
            size: file.size,
            kind,
        },
        { withCredentials: true },
    );

    const { objectKey, uploadUrl, headers } = uploadUrlResponse.data;
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
        { withCredentials: true },
    );

    return completeResponse.data.fileId;
}

export async function fetchDownloadUrl(fileId) {
    const response = await axios.get(`${appConfig.backendUrl}/api/files/${fileId}/download-url`, {
        withCredentials: true,
    });
    return response.data.downloadUrl;
}

export async function downloadByFileId(fileId) {
    const downloadUrl = await fetchDownloadUrl(fileId);
    window.location.href = downloadUrl;
}
