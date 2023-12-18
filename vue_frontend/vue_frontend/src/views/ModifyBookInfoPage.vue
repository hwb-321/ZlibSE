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
            <v-text-field label="作者" v-model="book.author" required></v-text-field>
            <v-text-field label="ISBN" v-model="book.isbn" required></v-text-field>
            <v-text-field label="种类" v-model="book.category" required></v-text-field>
            <v-text-field label="年份" v-model="book.year" type="number" required></v-text-field>
            <v-text-field label="语言" v-model="book.language" required></v-text-field>

            <v-file-input label="封面图片（留空表示不修改）" @change="handleCoverChange" accept="image/*"
                :placeholder="book.cover_image_path"></v-file-input>
            <v-file-input label="文件（留空表示不修改）" @change="handleFileChange" :placeholder="book.file_path"></v-file-input>

            <v-btn type="submit" color="primary" :disabled="!isFormValid">更新</v-btn>
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
                file_type: '',
                file_path: '',
                cover_image_path: ''
            },
            errorMessage: '',
            successMessage: '',
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
            return this.book.title && this.book.author && this.book.isbn &&
                this.book.category && this.book.year && this.book.language;
        }
    },
    methods: {
        async fetchBookData() {
            try {
                const bookId = this.$route.params.bookId; // 从路由获取bookId
                const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/get_descriptions/${bookId}`, { withCredentials: true });
                this.book = { ...response.data };
            } catch (error) {
                this.errorMessage = '加载书籍数据失败';
                console.error('Error fetching book details:', error);
            }
        },
        handleFileChange(event) {
            if (event.target.files.length > 0) {
                this.book.file_path = event.target.files[0];
            }
        },
        handleCoverChange(event) {
            if (event.target.files.length > 0) {
                this.book.cover_image_path = event.target.files[0];
            }
        },
        async updateBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请填写所有字段';
                return;
            }

            try {
                const formData = new FormData();
                Object.keys(this.book).forEach(key => {
                    if (this.book[key] !== null && key !== 'file_path' && key !== 'cover_image_path') {
                        formData.append(key, this.book[key]);
                    }
                });
                if (this.book.file_path instanceof File) {
                    formData.append('file_path', this.book.file_path);
                }
                if (this.book.cover_image_path instanceof File) {
                    formData.append('cover_image_path', this.book.cover_image_path);
                }

                const bookId = this.$route.params.bookId;
                await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/change_uploaded_book/${bookId}`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    withCredentials: true
                });
                this.successMessage = '书籍信息更新成功';
                this.errorMessage = '';
            } catch (error) {
                this.errorMessage = '更新书籍信息失败，请重试';
                console.error('Update error:', error);
            }
        }
    }
}
</script>