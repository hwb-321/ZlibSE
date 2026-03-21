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
            <v-text-field label="书名" v-model="book.title" required></v-text-field>
            <v-text-field label="作者" v-model="book.author"></v-text-field>
            <v-text-field label="ISBN" v-model="book.isbn"></v-text-field>
            <v-text-field label="种类" v-model="book.category"></v-text-field>
            <v-text-field label="年份" v-model="book.year" type="number"></v-text-field>
            <v-text-field label="语言" v-model="book.language"></v-text-field>

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
                :disabled="!isFormValid || fileErrors.length || coverErrors.length">上传</v-btn>
        </v-form>

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
import { uploadFileToStorage } from '@/utils/fileApi';

export default {
    data() {
        return {
            book: {
                title: '',
                author: '',
                isbn: '',
                category: '',
                year: '',
                language: '',
            },
            file_path: null,
            cover_image_path: null,
            fileErrors: [],
            coverErrors: [],
            errorMessage: '',
            successMessage: '',
            submitting: false,
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '上传书籍';
        });
    },
    computed: {
        isFormValid() {
            return this.book.title && this.file_path;
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
        async submitBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请至少填写书名并选择书籍文件';
                return;
            }

            this.submitting = true;
            this.errorMessage = '';
            this.successMessage = '';

            try {
                const bookFileId = await uploadFileToStorage(this.file_path, 'book');
                const coverFileId = this.cover_image_path
                    ? await uploadFileToStorage(this.cover_image_path, 'cover')
                    : null;

                await axios.post(
                    `${appConfig.backendUrl}/api/books`,
                    {
                        title: this.book.title,
                        author: this.book.author || null,
                        isbn: this.book.isbn || null,
                        category: this.book.category || null,
                        year: this.book.year ? Number(this.book.year) : null,
                        language: this.book.language || null,
                        bookFileId,
                        coverFileId,
                    },
                    { withCredentials: true },
                );

                this.successMessage = '上传成功';
                this.book = {
                    title: '',
                    author: '',
                    isbn: '',
                    category: '',
                    year: '',
                    language: '',
                };
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
