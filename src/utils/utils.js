import { buildBackendUrl } from '@/utils/fileApi';

export function getCoverUrl(coverPath) {
    return buildBackendUrl(coverPath);
}
