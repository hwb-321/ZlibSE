<template>
    <div class="uploaded-book-management">
        <div class="header">
            <h1>我上传的书籍管理</h1>
            <!-- 添加 router-link 按钮 -->
            <router-link to="/upload-book" class="upload-book-button">上传书籍</router-link>
        </div>

        <!-- 搜索框和搜索按钮 -->
        <div class="search-container">
            <input v-model="searchQuery" @keyup.enter="searchUploadedBooks" placeholder="搜索上传的书籍...">
            <button @click="searchUploadedBooks">搜索</button>
        </div>

        <!-- 书籍列表 -->
        <BookCardWithDelete v-for="book in uploadedBooks" :key="book.id" :book="book" @bookDeleted="handleBookDeleted" />

        <!-- 返回主界面按钮 -->
        <button @click="goToHome">返回主界面</button>
    </div>
</template>
  
<script>
import axios from 'axios';
import BookCardWithDelete from '../components/BookCardWithDelete.vue';

export default {
    name: 'UploadedBookManagementPage',
    components: {
        BookCardWithDelete
    },
    data() {
        return {
            uploadedBooks: [],
            searchQuery: ''
        };
    },
    methods: {
        goToHome() {
            this.$router.push('/home');
        },
        async fetchUploadedBooks() {
            try {
                const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/user/get_upload_book_list`, {
                    withCredentials: true
                });
                this.uploadedBooks = response.data.uploadedBooks;
            } catch (error) {
                console.error('Error fetching uploaded books:', error);
            }
        },
        async searchUploadedBooks() {
            if (this.searchQuery.trim()) {
                try {
                    const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/search`, {
                        params: { query: this.searchQuery },
                        withCredentials: true
                    });
                    this.uploadedBooks = response.data.books;
                } catch (error) {
                    console.error('Error searching books:', error);
                }
            } else {
                this.fetchUploadedBooks();
            }
        },
        async handleBookDeleted() {
            await this.fetchUploadedBooks();
        }
    },
    created() {
        this.fetchUploadedBooks();
    }
};
</script>
  
<style scoped>
.uploaded-book-management {
    margin: 20px;
    position: relative;
}

.search-container {
    margin-bottom: 20px;
}

.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.upload-book-button {
    padding: 10px 15px;
    background-color: #0056b3;
    color: white;
    text-decoration: none;
    border-radius: 5px;
    text-align: center;
}
</style>
