<template>
    <div class="book-detail">
        <div class="book-cover">
            <img :src="coverImage" alt="Book Cover" />
        </div>
        <div class="book-info">
            <h2>{{ title }}</h2>
            <div class="book-meta">
                <span>作者: {{ author }}</span>
                <span>ISBN: {{ isbn }}</span>
                <span>种类: {{ category }}</span>
                <span>年份: {{ year }}</span>
                <span>语言: {{ language }}</span>
                <span>文件类型: {{ file_type }}</span>
                <span>文件大小: {{ formattedFileSize }}</span>
            </div>
            <button @click="downloadBook">下载</button>
            <button @click="toggleFavorite">{{ isFavorited ? '取消收藏' : '收藏' }}</button>
        </div>
    </div>
</template>
  
<script>
import axios from 'axios';

export default {
    props: {
        bookId: {
            type: Number,
            required: true
        }
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
            file_path: '',
            coverImage: '',
            file_size: null,
            isFavorited: false,
        };
    },
    computed: {
        // 计算属性，用于格式化文件大小显示
        formattedFileSize() {
            const fileSizeNum = parseFloat(this.file_size);  // 将 file_size 字符串转换为数字
            if (!isNaN(fileSizeNum)) {
                if (fileSizeNum >= 1024) {
                    // 文件大小大于或等于 1024MB，转换为 GB
                    return (fileSizeNum / 1024).toFixed(1) + ' GB';
                } else {
                    // 文件大小小于 1024MB，保持 MB 显示
                    return fileSizeNum.toFixed(1) + ' MB';
                }
            }
            return '';  // 如果 file_size 不是数字，则返回空字符串
        }
    },
    created() {
        this.fetchBookDetails();
    },
    methods: {
        async fetchBookDetails() {
            try {
                const response = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/book/get_descriptions/${this.$route.params.id}`, { withCredentials: true });

                const bookData = response.data;
                this.title = bookData.title;
                this.author = bookData.author;
                this.isbn = bookData.isbn;
                this.category = bookData.category;
                this.year = bookData.year;
                this.language = bookData.language;
                this.file_type = bookData.file_type;
                this.file_size = bookData.file_size;
                this.coverImage = this.$getCoverUrl(this.$route.params.id);

                const favoriteResponse = await axios.get(`${process.env.VUE_APP_BACKEND_URL}/user/check_favorite/${this.$route.params.id}`, { withCredentials: true });
                this.isFavorited = favoriteResponse.data.isFavorited;
            } catch (error) {
                console.error('Error fetching book details:', error);
            }
        },
        downloadBook() {
            const downloadUrl = `${process.env.VUE_APP_BACKEND_URL}/book/download/${this.$route.params.id}`;
            window.location.href = downloadUrl;
        },
        async addToFavorites() {
            try {
                const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/add_to_favorites/${this.$route.params.id}`, {}, {
                    withCredentials: true
                });

                if (response.data.success) {
                    // 处理收藏成功的情况
                    alert('书籍收藏成功！');
                } else {
                    // 处理收藏失败的情况
                    alert(response.data.message);
                }
            } catch (error) {
                console.error('Error adding book to favorites:', error);
                alert('收藏书籍时发生错误');
            }
        },
        async toggleFavorite() {
            try {
                let response;
                if (this.isFavorited) {
                    // 如果当前已收藏，发送取消收藏的请求
                    response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/remove_from_favorites/${this.$route.params.id}`, {}, { withCredentials: true });
                } else {
                    // 如果当前未收藏，发送添加收藏的请求
                    response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/add_to_favorites/${this.$route.params.id}`, {}, { withCredentials: true });
                }

                if (response.data.success) {
                    this.isFavorited = !this.isFavorited; // 切换收藏状态
                } else {
                    alert(response.data.message);
                }
            } catch (error) {
                console.error('Error toggling favorite status:', error);
                alert('操作失败');
            }
        },
    }
};
</script>
  
<style scoped>
.book-detail {
    display: flex;
    margin: 20px;
}

.book-cover img {
    max-width: 200px;
    margin-right: 20px;
}

.book-info {
    flex: 1;
}

.book-meta {
    margin-bottom: 10px;
}

.book-meta span {
    display: block;
    margin-bottom: 5px;
}

button {
    padding: 10px 20px;
    cursor: pointer;
    background-color: #0056b3;
    color: white;
    border: none;
    border-radius: 5px;
}
</style>
  