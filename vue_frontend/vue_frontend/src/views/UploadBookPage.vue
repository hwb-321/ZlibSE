<template>
    <div class="upload-book-container">
        <h1>上传书籍</h1>
        <form @submit.prevent="submitBook">
            <div>
                <label for="title">书名:</label>
                <input id="title" v-model="book.title" type="text" required>
            </div>
            <div>
                <label for="author">作者:</label>
                <input id="author" v-model="book.author" type="text" required>
            </div>
            <div>
                <label for="isbn">ISBN:</label>
                <input id="isbn" v-model="book.isbn" type="text" required>
            </div>
            <div>
                <label for="category">种类:</label>
                <input id="category" v-model="book.category" type="text" required>
            </div>
            <div>
                <label for="year">年份:</label>
                <input id="year" v-model="book.year" type="number" required>
            </div>
            <div>
                <label for="language">语言:</label>
                <input id="language" v-model="book.language" type="text" required>
            </div>
            <div>
                <label for="cover">封面图片:</label>
                <input id="cover" type="file" @change="handleCoverChange" accept="image/*">
            </div>
            <div>
                <label for="file">文件:</label>
                <input id="file" type="file" @change="handleFileChange">
            </div>
            <button type="submit">上传</button>
        </form>
        <div v-if="message">{{ message }}</div>
    </div>
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
            message: ''
        };
    },
    methods: {
        handleFileChange(event) {
            this.file_path = event.target.files[0];
        },
        handleCoverChange(event) {
            this.cover_image_path = event.target.files[0];
        },
        async submitBook() {
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

                await axios.post(`${process.env.VUE_APP_BACKEND_URL}/book/upload_book/`, formData, {
                    headers: {
                        'Content-Type': 'multipart/form-data'
                    },
                    withCredentials: true
                });
                this.message = '上传成功';
            } catch (error) {
                console.error('Upload error:', error);
                this.message = '上传失败，请重试。';
            }
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
  