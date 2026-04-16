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
                先上传正文并等待后端解析，解析完成后可以修改元数据和封面，再确认创建书籍。
            </v-alert>

            <v-file-input
                label="文件"
                @update:modelValue="handleFileChange"
                :disabled="Boolean(parsedDraft)"
                :error-messages="fileErrors"
            ></v-file-input>

            <v-btn v-if="!parsedDraft" type="submit" color="primary" :loading="submitting"
                :disabled="!isFormValid || fileErrors.length">上传并解析</v-btn>
            <v-btn
                v-if="pendingParseFileId && !parsedDraft"
                color="secondary"
                variant="outlined"
                class="ml-2"
                :loading="checkingPendingParse"
                @click="resumeParseCheck"
            >
                继续检查解析结果
            </v-btn>
            <v-btn v-if="parsedDraft" color="secondary" variant="outlined" class="mr-2" @click="resetParsedDraft">
                重新选择正文
            </v-btn>
        </v-form>

        <v-card v-if="parsedDraft" class="mt-4" variant="outlined">
            <v-card-title>确认书籍信息</v-card-title>
            <v-card-text>
                <div class="mb-3">解析状态：{{ parsedDraft.statusText }}</div>
                <v-img
                    v-if="autoCoverPreviewUrl"
                    :src="autoCoverPreviewUrl"
                    alt="自动提取封面"
                    height="320"
                    contain
                    class="mb-4"
                ></v-img>
                <v-text-field label="书名（可留空）" v-model="parsedDraft.title"></v-text-field>
                <v-text-field label="作者" v-model="parsedDraft.author"></v-text-field>
                <v-text-field label="ISBN" v-model="parsedDraft.isbn"></v-text-field>
                <v-text-field label="分类" v-model="parsedDraft.category"></v-text-field>
                <v-text-field label="年份" v-model="parsedDraft.year" type="number"></v-text-field>
                <v-text-field label="语言" v-model="parsedDraft.language"></v-text-field>

                <div class="mb-3">
                    自动封面：{{ parsedDraft.autoCoverFileId ? `已生成（ID: ${parsedDraft.autoCoverFileId}）` : '未解析到' }}
                </div>

                <v-file-input
                    label="手动上传封面（可选）"
                    @update:modelValue="handleCoverChange"
                    accept="image/*"
                    :error-messages="coverErrors"
                ></v-file-input>

                <v-btn color="primary" :loading="creating" :disabled="!canCreateBook || coverErrors.length" @click="createBook">
                    确认创建书籍
                </v-btn>
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
import {
    fetchDownloadUrl,
    fetchParseResult,
    uploadBookFileAndWaitForParse,
    uploadFileToStorage,
    waitForParseResult,
} from '@/utils/fileApi';

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
            creating: false,
            checkingPendingParse: false,
            parsedDraft: null,
            autoCoverPreviewUrl: '',
            pendingParseFileId: null,
            pendingParseFileName: '',
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '上传书籍';
        });
    },
    beforeUnmount() {
        this.revokeAutoCoverPreview();
    },
    computed: {
        isFormValid() {
            return Boolean(this.file_path);
        },
        canCreateBook() {
            return Boolean(this.parsedDraft?.storedFileId);
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
                this.parsedDraft = null;
                this.pendingParseFileId = null;
                this.pendingParseFileName = '';
                this.revokeAutoCoverPreview();
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
        buildBookPayload(coverFileId) {
            if (!this.parsedDraft) {
                return null;
            }
            const normalizedYear = this.parsedDraft.year === '' || this.parsedDraft.year === null
                ? null
                : Number(this.parsedDraft.year);
            return {
                storedFileId: this.parsedDraft.storedFileId,
                title: this.parsedDraft.title || null,
                author: this.parsedDraft.author || null,
                isbn: this.parsedDraft.isbn || null,
                category: this.parsedDraft.category || null,
                year: Number.isNaN(normalizedYear) ? null : normalizedYear,
                language: this.parsedDraft.language || null,
                coverFileId,
            };
        },
        buildDraft(file, parseResult, storedFileId) {
            return {
                storedFileId,
                title: parseResult?.title || file?.name?.replace(/\.[^.]+$/, '') || '',
                author: parseResult?.author || '',
                isbn: '',
                category: '',
                year: '',
                language: parseResult?.language || '',
                autoCoverFileId: parseResult?.coverFileId || null,
                statusText: parseResult?.errorMessage ? '解析完成，部分信息需要手动确认' : '解析完成',
            };
        },
        resetParsedDraft() {
            this.revokeAutoCoverPreview();
            this.parsedDraft = null;
            this.cover_image_path = null;
            this.coverErrors = [];
            this.successMessage = '';
            this.errorMessage = '';
            this.pendingParseFileId = null;
            this.pendingParseFileName = '';
            this.checkingPendingParse = false;
        },
        revokeAutoCoverPreview() {
            this.autoCoverPreviewUrl = '';
        },
        async loadAutoCoverPreview(coverFileId) {
            this.revokeAutoCoverPreview();
            if (!coverFileId) {
                return;
            }
            try {
                this.autoCoverPreviewUrl = await fetchDownloadUrl(coverFileId);
            } catch (error) {
                console.error('加载自动封面预览失败:', error);
            }
        },
        async submitBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请选择书籍文件';
                return;
            }

            this.submitting = true;
            this.errorMessage = '';
            this.successMessage = '';
            this.parsedDraft = null;
            this.pendingParseFileId = null;
            this.pendingParseFileName = '';

            try {
                const uploadResult = await uploadBookFileAndWaitForParse(this.file_path, {
                    timeoutMs: 180000,
                    intervalMs: 1000,
                });
                if (uploadResult.parseResult?.parseStatus !== 'done') {
                    this.pendingParseFileId = uploadResult.fileId;
                    this.pendingParseFileName = this.file_path?.name || '';
                    throw new Error('正文仍在解析中，请稍后继续检查结果。');
                }
                this.parsedDraft = this.buildDraft(this.file_path, uploadResult.parseResult, uploadResult.fileId);
                await this.loadAutoCoverPreview(this.parsedDraft.autoCoverFileId);
            } catch (error) {
                console.error('Upload error:', error);
                this.errorMessage = error.response?.data?.message || error.message || '上传失败，请重试。';
            } finally {
                this.submitting = false;
            }
        },
        async resumeParseCheck() {
            if (!this.pendingParseFileId) {
                return;
            }
            this.checkingPendingParse = true;
            this.errorMessage = '';
            this.successMessage = '';
            try {
                let parseResult = await fetchParseResult(this.pendingParseFileId);
                if (parseResult?.parseStatus !== 'done') {
                    parseResult = await waitForParseResult(this.pendingParseFileId, {
                        timeoutMs: 180000,
                        intervalMs: 1000,
                    });
                }
                if (parseResult?.parseStatus !== 'done') {
                    throw new Error('正文仍在解析中，请稍后继续检查。');
                }
                const draftFile = this.file_path || { name: this.pendingParseFileName };
                this.parsedDraft = this.buildDraft(draftFile, parseResult, this.pendingParseFileId);
                this.pendingParseFileId = null;
                this.pendingParseFileName = '';
                await this.loadAutoCoverPreview(this.parsedDraft.autoCoverFileId);
            } catch (error) {
                console.error('Resume parse error:', error);
                this.errorMessage = error.response?.data?.message || error.message || '检查解析结果失败，请稍后重试。';
            } finally {
                this.checkingPendingParse = false;
            }
        },
        async createBook() {
            if (!this.canCreateBook) {
                this.errorMessage = '请先等待解析完成';
                return;
            }

            this.creating = true;
            this.errorMessage = '';
            this.successMessage = '';

            try {
                const coverFileId = this.cover_image_path
                    ? await uploadFileToStorage(this.cover_image_path, 'cover')
                    : this.parsedDraft.autoCoverFileId;
                const payload = this.buildBookPayload(coverFileId);
                const createResponse = await axios.post(`${appConfig.backendUrl}/api/books`, payload);

                this.successMessage = `上传成功，已创建《${createResponse.data.book.title}》`;
                this.file_path = null;
                this.cover_image_path = null;
                this.revokeAutoCoverPreview();
                this.parsedDraft = null;
                this.pendingParseFileId = null;
                this.pendingParseFileName = '';
            } catch (error) {
                console.error('Create book error:', error);
                this.errorMessage = error.response?.data?.message || error.message || '创建书籍失败，请重试。';
            } finally {
                this.creating = false;
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
