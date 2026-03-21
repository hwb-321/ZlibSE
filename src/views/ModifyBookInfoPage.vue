<template>
    <v-container>
        <v-row>
            <v-col cols="12" class="d-flex justify-space-around align-center mb-3">
                <h1>修改书籍信息</h1>
                <router-link to="/uploaded-book-management">
                    <v-btn color="secondary">返回上传管理</v-btn>
                </router-link>
            </v-col>
        </v-row>

        <v-form @submit.prevent="updateBook">
            <v-text-field label="书名" v-model="book.title" required></v-text-field>
            <v-text-field label="作者" v-model="book.author"></v-text-field>
            <v-text-field label="ISBN" v-model="book.isbn"></v-text-field>
            <v-text-field label="种类" v-model="book.category"></v-text-field>
            <v-text-field label="年份" v-model="book.year" type="number"></v-text-field>
            <v-text-field label="语言" v-model="book.language"></v-text-field>

            <v-file-input
                label="封面图片（留空表示不修改）"
                @update:modelValue="handleCoverChange"
                accept="image/*"
                :placeholder="book.coverFileId ? '封面图片已上传' : '未上传封面图片'"
                :error-messages="coverErrors"
            ></v-file-input>
            <v-file-input
                label="文件（留空表示不修改）"
                @update:modelValue="handleFileChange"
                :placeholder="book.bookFileId ? '文件已上传' : '未上传文件'"
                :error-messages="fileErrors"
            ></v-file-input>

            <v-btn type="submit" color="primary" :loading="submitting"
                :disabled="!isFormValid || fileErrors.length || coverErrors.length">更新</v-btn>
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
                bookFileId: null,
                coverFileId: null,
            },
            selectedBookFile: null,
            selectedCoverFile: null,
            errorMessage: '',
            successMessage: '',
            fileErrors: [],
            coverErrors: [],
            submitting: false,
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '修改书籍信息';
            this.fetchBookData();
        });
    },
    computed: {
        isFormValid() {
            return this.book.title && this.book.bookFileId;
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
        async fetchBookData() {
            try {
                const bookId = this.$route.params.bookId;
                const response = await axios.get(`${appConfig.backendUrl}/book/get_descriptions/${bookId}`, {
                    withCredentials: true,
                });
                const data = response.data;
                this.book = {
                    title: data.title || '',
                    author: data.author || '',
                    isbn: data.isbn || '',
                    category: data.category || '',
                    year: data.year || '',
                    language: data.language || '',
                    bookFileId: data.book_file_id,
                    coverFileId: data.cover_file_id,
                };
            } catch (error) {
                this.errorMessage = '加载书籍数据失败';
                console.error('Error fetching book details:', error);
            }
        },
        handleFileChange(payload) {
            const file = this.normalizeFile(payload);
            if (file) {
                if (file.size <= 1024 * 1024 * 1024) {
                    this.selectedBookFile = file;
                    this.fileErrors = [];
                } else {
                    this.selectedBookFile = null;
                    this.fileErrors = ['书籍文件大小不能超过1G'];
                }
            } else {
                this.selectedBookFile = null;
                this.fileErrors = [];
            }
        },
        handleCoverChange(payload) {
            const file = this.normalizeFile(payload);
            if (file) {
                if (file.size <= 20 * 1024 * 1024) {
                    this.selectedCoverFile = file;
                    this.coverErrors = [];
                } else {
                    this.selectedCoverFile = null;
                    this.coverErrors = ['封面图片大小不能超过20M'];
                }
            } else {
                this.selectedCoverFile = null;
                this.coverErrors = [];
            }
        },
        async updateBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请填写必要字段';
                return;
            }

            this.submitting = true;
            this.errorMessage = '';
            this.successMessage = '';

            try {
                let bookFileId = this.book.bookFileId;
                let coverFileId = this.book.coverFileId;

                if (this.selectedBookFile) {
                    bookFileId = await uploadFileToStorage(this.selectedBookFile, 'book');
                }
                if (this.selectedCoverFile) {
                    coverFileId = await uploadFileToStorage(this.selectedCoverFile, 'cover');
                }

                const bookId = this.$route.params.bookId;
                await axios.put(
                    `${appConfig.backendUrl}/api/books/${bookId}`,
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

                this.book.bookFileId = bookFileId;
                this.book.coverFileId = coverFileId;
                this.selectedBookFile = null;
                this.selectedCoverFile = null;
                this.successMessage = '书籍信息更新成功';
            } catch (error) {
                this.errorMessage = error.response?.data?.message || error.message || '更新书籍信息失败，请重试';
                console.error('Update error:', error);
            } finally {
                this.submitting = false;
            }
        },
    },
};
</script>
