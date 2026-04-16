import { resolveFileAccessUrl } from '@/utils/fileApi';

export function getCoverUrl(coverPath) {
    return resolveFileAccessUrl(coverPath);
}
