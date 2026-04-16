<template>
    <v-container>
        <v-row align="center" justify="center">
            <v-col cols="12" md="6">
                <v-img :src="coverImage" alt="Book Cover" height="50vh" contain></v-img>
            </v-col>
            <v-col cols="12" md="6">
                <v-card class="book-info" height="auto">
                    <div class="text-md-center text-center">
                        <v-card-title>{{ title }}</v-card-title>
                        <v-card-subtitle>{{ author }}</v-card-subtitle>
                    </div>
                    <v-card-text class="text-md-left text-center">
                        <div>ISBN: {{ isbn || '暂无' }}</div>
                        <div>种类: {{ category || '暂无' }}</div>
                        <div>年份: {{ year || '暂无' }}</div>
                        <div>语言: {{ language || '暂无' }}</div>
                        <div>文件类型: {{ file_type || '未知' }}</div>
                        <div>文件大小: {{ formattedFileSize || '未知' }}</div>
                    </v-card-text>
                    <v-card-actions class="justify-space-between">
                        <v-btn color="primary" variant="outlined" @click="downloadBook">
                            <v-icon left>mdi-download</v-icon>
                            下载
                        </v-btn>
                        <v-btn v-if="file_type === 'epub'" color="info" variant="outlined" @click="openOnlineReader">
                            <v-icon left>mdi-book-open-variant</v-icon>
                            在线阅读
                        </v-btn>
                        <v-btn color="secondary" variant="outlined" @click="toggleFavorite">
                            <v-icon left>{{ isFavorited ? 'mdi-heart' : 'mdi-heart-outline' }}</v-icon>
                            {{ isFavorited ? '取消收藏' : '收藏' }}
                        </v-btn>
                    </v-card-actions>
                </v-card>
            </v-col>
        </v-row>
    </v-container>
</template>

<script>
import axios from 'axios';
import appConfig from '@/config/appConfig.json';
import { downloadByFileId, resolveFileAccessUrl } from '@/utils/fileApi';
import { hasAccessToken } from '@/utils/auth';

export default {
    props: {
        bookId: {
            type: Number,
            required: true,
        },
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '书籍详情';
        });
    },
    data() {
        return {
            title: '',
            author: '',
            isbn: '',
            category: '',
            year: null,
            language: '',
            file_type: '',
            file_size: null,
            book_file_id: null,
            cover_file_id: null,
            cover_path: '',
            coverImage: '',
            isFavorited: false,
        };
    },
    computed: {
        formattedFileSize() {
            const fileSizeNum = parseFloat(this.file_size);
            if (!Number.isNaN(fileSizeNum)) {
                if (fileSizeNum >= 1024) {
                    return `${(fileSizeNum / 1024).toFixed(1)} GB`;
                }
                return `${fileSizeNum.toFixed(1)} MB`;
            }
            return '';
        },
    },
    created() {
        this.fetchBookDetails();
    },
    methods: {
        async fetchBookDetails() {
            try {
                const response = await axios.get(`${appConfig.backendUrl}/api/books/${this.bookId}`);

                const bookData = response.data;
                this.title = bookData.title;
                this.author = bookData.author;
                this.isbn = bookData.isbn;
                this.category = bookData.category;
                this.year = bookData.year;
                this.language = bookData.language;
                this.file_type = bookData.file_type;
                this.file_size = bookData.file_size;
                this.book_file_id = bookData.book_file_id;
                this.cover_file_id = bookData.cover_file_id;
                this.cover_path = bookData.cover_image_path;
                this.coverImage = await resolveFileAccessUrl(bookData.cover_image_path);
            } catch (error) {
                console.error('Error fetching book details:', error);
                return;
            }

            if (!hasAccessToken()) {
                this.isFavorited = false;
                return;
            }

            try {
                const favoriteResponse = await axios.get(`${appConfig.backendUrl}/api/users/me/favorites/${this.bookId}`);
                this.isFavorited = favoriteResponse.data.isFavorited;
            } catch (error) {
                console.error('Error fetching favorite status:', error);
                this.isFavorited = false;
            }
        },
        async downloadBook() {
            if (!this.book_file_id) {
                alert('当前书籍缺少可下载文件');
                return;
            }
            try {
                await downloadByFileId(this.book_file_id);
            } catch (error) {
                console.error('Download error:', error);
                alert('下载失败');
            }
        },
        async toggleFavorite() {
            try {
                let response;
                if (this.isFavorited) {
                    response = await axios.delete(`${appConfig.backendUrl}/api/users/me/favorites/${this.bookId}`);
                } else {
                    response = await axios.post(`${appConfig.backendUrl}/api/users/me/favorites/${this.bookId}`, {});
                }

                if (response.data.success) {
                    this.isFavorited = !this.isFavorited;
                } else {
                    this.$router.push({ name: 'LoginPage' });
                }
            } catch (error) {
                if (this.$route.name !== 'LoginPage') {
                    this.$router.push({ name: 'LoginPage' });
                }
            }
        },
        openOnlineReader() {
            if (!this.book_file_id) {
                alert('当前书籍缺少可阅读文件');
                return;
            }
            const readerUrl = `/online-reader-epub?bookId=${this.bookId}&fileId=${this.book_file_id}`;
            window.open(readerUrl, '_blank');
        },
    },
};
</script>

<style scoped>
.book-info {
    display: flex;
    flex-direction: column;
}

@media only screen and (min-width: 960px) {
    .book-info {
        align-items: flex-start;
    }

    .book-info > .text-md-center {
        text-align: center;
    }

    .book-info > .text-md-left {
        text-align: left;
    }
}
</style>
