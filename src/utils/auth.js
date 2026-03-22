import { reactive } from 'vue';

const ACCESS_TOKEN_KEY = 'zlibse_access_token';

export const authState = reactive({
    accessToken: window.localStorage.getItem(ACCESS_TOKEN_KEY) || '',
});

export function getAccessToken() {
    return authState.accessToken;
}

export function setAccessToken(token) {
    if (!token) {
        clearAccessToken();
        return;
    }
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token);
    authState.accessToken = token;
}

export function clearAccessToken() {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY);
    authState.accessToken = '';
}

export function hasAccessToken() {
    return Boolean(authState.accessToken);
}
