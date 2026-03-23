<template>
    <v-container>
        <v-row align="center" class="mb-3">
            <v-col cols="12" md="8" class="text-md-left text-center">
                <h1>上传书籍管理</h1>
            </v-col>
            <v-col cols="12" md="4" class="text-md-right text-center">
                <router-link to="/upload-book" class="mr-2">
                    <v-btn color="primary">上传书籍</v-btn>
                </router-link>
                <router-link to="/personal-center">
                    <v-btn color="primary">返回个人中心</v-btn>
                </router-link>
            </v-col>
        </v-row>

        <!-- 搜索框 -->
        <v-row justify="center">
            <v-col cols="12" md="8">
                <v-text-field v-model="searchQuery" @keyup.enter="searchUploadedBooks" placeholder="搜索上传的书籍..."
                    append-icon="mdi-magnify" @click:append="searchUploadedBooks" solo></v-text-field>
            </v-col>
        </v-row>

        <!-- 书籍列表 -->
        <v-row>
            <v-col cols="12" sm="6" md="4" v-for="book in uploadedBooks" :key="book.id">
                <BookCardWithDelete :book="book" @bookDeleted="handleBookDeleted" />
            </v-col>
        </v-row>
    </v-container>
</template>
  
  
<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import BookCardWithDelete from '../components/BookCardWithDelete.vue';

export default {
    name: 'UploadedBookManagementPage',
    components: {
        BookCardWithDelete
    },
    data() {
        return {
            uploadedBooks: [],
            allUploadedBooks: [],
            searchQuery: ''
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '上传书籍管理';
        });
    },
    methods: {
        goToPersonalCenter() {
            this.$router.push('/personal-center');
        },
        async fetchUploadedBooks() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/user/get_upload_book_list`);
                this.uploadedBooks = response.data.uploadedBooks;
                this.allUploadedBooks = response.data.uploadedBooks;
            } catch (error) {
                console.error('Error fetching uploaded books:', error);
            }
        },
        searchUploadedBooks() {
            const query = this.searchQuery.trim().toLowerCase();
            if (!query) {
                this.uploadedBooks = this.allUploadedBooks;
                return;
            }
            this.uploadedBooks = this.allUploadedBooks.filter((book) => {
                return [
                    book.title,
                    book.author,
                    book.isbn,
                    book.category,
                    book.year,
                    book.language,
                    book.file_type,
                ].some((value) => String(value || '').toLowerCase().includes(query));
            });
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
