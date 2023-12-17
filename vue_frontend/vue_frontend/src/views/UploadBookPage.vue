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
            <v-text-field label="作者" v-model="book.author" required></v-text-field>
            <v-text-field label="ISBN" v-model="book.isbn" required></v-text-field>
            <v-text-field label="种类" v-model="book.category" required></v-text-field>
            <v-text-field label="年份" v-model="book.year" type="number" required></v-text-field>
            <v-text-field label="语言" v-model="book.language" required></v-text-field>

            <v-file-input label="封面图片" @change="handleCoverChange" accept="image/*"></v-file-input>
            <v-file-input label="文件" @change="handleFileChange"></v-file-input>

            <v-btn type="submit" color="primary" :disabled="!isFormValid">上传</v-btn>
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
            },
            file_path: null,
            cover_image_path: null,
            errorMessage: '',
            successMessage: '',
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '上传书籍';
        });
    },
    computed: {
        isFormValid() {
            return this.book.title && this.book.author && this.book.isbn &&
                this.book.category && this.book.year && this.book.language &&
                this.file_path && this.cover_image_path;
        }
    },
    methods: {
        handleFileChange(event) {
            this.file_path = event.target.files[0];
        },
        handleCoverChange(event) {
            this.cover_image_path = event.target.files[0];
        },
        async submitBook() {
            if (!this.isFormValid) {
                this.errorMessage = '请填写所有字段';
                return;
            }

            try {
                const formData = new FormData();
                Object.keys(this.book).forEach(key => {
                    formData.append(key, this.book[key]);
                });
                if (this.file_path) {
                    formData.append('file_path', this.file_path);
                }
                if (this.cover_image_path) {
                    formData.append('cover_image_path', this.cover_image_path);
                }

                await axios.post(`${process.env.VUE_APP_BACKEND_URL}/book/upload_book`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    withCredentials: true
                });
                this.successMessage = '上传成功';
                this.errorMessage = '';
            } catch (error) {
                console.error('Upload error:', error);
                this.errorMessage = '上传失败，请重试。';
                this.successMessage = '';
            }
        },
        showMessage(msg) {
            this.message = msg;
            setTimeout(() => {
                this.message = '';
            }, 2000); // 2秒后消息消失
        },
    }
};
</script>
  
<style scoped>
.upload-book-container {
    margin: 20px;
}

/* 更多样式可以在这里添加 */
</style>
  