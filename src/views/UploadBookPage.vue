<template>
    <v-container>
        <v-row>
            <v-col cols="12" class="d-flex justify-space-around align-center mb-3">
                <h1>上传书籍</h1>
                <router-link to="/uploaded-book-management">
                    <v-btn color="secondary">返回上传管理</v-btn>
                </router-link>
            </v-col>
        </v-row>

        <v-form @submit.prevent="submitBook">
            <v-alert type="info" variant="tonal" class="mb-4">
                书名、作者、语言等基础信息将由后端自动解析并回填，上传时无需手动填写。
            </v-alert>

            <v-file-input
                label="封面图片（可选）"
                @update:modelValue="handleCoverChange"
                accept="image/*"
                :error-messages="coverErrors"
            ></v-file-input>
            <v-file-input
                label="文件"
                @update:modelValue="handleFileChange"
                :error-messages="fileErrors"
            ></v-file-input>

            <v-btn type="submit" color="primary" :loading="submitting"
                :disabled="!isFormValid || fileErrors.length || coverErrors.length">上传并创建书籍</v-btn>
        </v-form>

        <v-card v-if="parsedBookPreview" class="mt-4" variant="outlined">
            <v-card-title>自动解析结果</v-card-title>
            <v-card-text>
                <div>书名：{{ parsedBookPreview.title || '未解析到，已使用文件名兜底' }}</div>
                <div>作者：{{ parsedBookPreview.author || '未解析到' }}</div>
                <div>语言：{{ parsedBookPreview.language || '未解析到' }}</div>
                <div>状态：{{ parsedBookPreview.statusText }}</div>
            </v-card-text>
        </v-card>

        <v-alert type="error" v-if="errorMessage" class="mt-4">
            {{ errorMessage }}
        </v-alert>

        <v-alert type="success" v-if="successMessage" class="mt-4">
            {{ successMessage }}
        </v-alert>
    </v-container>
</template>

<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import { uploadBookFileAndWaitForParse, uploadFileToStorage } from '@/utils/fileApi';

export default {
    data() {
        return {
            file_path: null,
            cover_image_path: null,
            fileErrors: [],
            coverErrors: [],
            errorMessage: '',
            successMessage: '',
            submitting: false,
            parsedBookPreview: null,
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '上传书籍';
        });
    },
    computed: {
        isFormValid() {
            return Boolean(this.file_path);
        },
    },
    methods: {
        normalizeFile(payload) {
            if (!payload) {
                return null;
            }
            if (Array.isArray(payload)) {
                return payload[0] || null;
            }
            return payload instanceof File ? payload : null;
        },
        handleFileChange(payload) {
            const file = this.normalizeFile(payload);
            if (file && file.size > 1024 * 1024 * 1024) {
                this.fileErrors = ['书籍大小不能超过1G'];
                this.file_path = null;
            } else {
                this.file_path = file;
                this.fileErrors = [];
                this.parsedBookPreview = null;
            }
        },
        handleCoverChange(payload) {
            const file = this.normalizeFile(payload);
            if (file && file.size > 20 * 1024 * 1024) {
                this.coverErrors = ['封面图片大小不能超过20M'];
                this.cover_image_path = null;
            } else {
                this.cover_image_path = file;
                this.coverErrors = [];
            }
        },
        buildBookPayload(file, parseResult, bookFileId, coverFileId) {
            const fallbackTitle = file?.name?.replace(/\.[^.]+$/, '') || '未命名书籍';
            return {
                title: parseResult?.title || fallbackTitle,
                author: parseResult?.author || null,
                isbn: null,
                category: null,
                year: null,
                language: parseResult?.language || null,
                bookFileId,
                coverFileId,
            };
        },
        buildPreview(file, parseResult) {
            const statusMap = {
                done: '解析完成',
                failed: '解析失败，已使用文件名兜底',
                dispatch_failed: '解析任务派发失败，已使用文件名兜底',
                missing: '暂无解析结果，已使用文件名兜底',
                timeout: '解析超时，已使用文件名兜底',
                unknown: '已复用已有文件，未额外轮询解析结果',
            };
            return {
                title: parseResult?.title || file?.name?.replace(/\.[^.]+$/, '') || '',
                author: parseResult?.author || '',
                language: parseResult?.language || '',
                statusText: statusMap[parseResult?.status] || '已使用默认结果',
            };
        },
        async submitBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请选择书籍文件';
                return;
            }

            this.submitting = true;
            this.errorMessage = '';
            this.successMessage = '';
            this.parsedBookPreview = null;

            try {
                const uploadResult = await uploadBookFileAndWaitForParse(this.file_path, {
                    timeoutMs: 15000,
                    intervalMs: 1000,
                });
                const bookFileId = uploadResult.fileId;
                const coverFileId = this.cover_image_path
                    ? await uploadFileToStorage(this.cover_image_path, 'cover')
                    : null;
                const payload = this.buildBookPayload(this.file_path, uploadResult.parseResult, bookFileId, coverFileId);

                await axios.post(
                    `${appConfig.backendUrl}/api/books`,
                    payload,
                );

                this.parsedBookPreview = this.buildPreview(this.file_path, uploadResult.parseResult);
                this.successMessage = `上传成功，已自动创建《${payload.title}》`;
                this.file_path = null;
                this.cover_image_path = null;
            } catch (error) {
                console.error('Upload error:', error);
                this.errorMessage = error.response?.data?.message || error.message || '上传失败，请重试。';
            } finally {
                this.submitting = false;
            }
        },
    },
};
</script>

<style scoped>
.upload-book-container {
    margin: 20px;
}
</style>
