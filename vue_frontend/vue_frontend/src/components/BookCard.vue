<template>
    <router-link :to="{ name: 'BookDetail', params: { id: book.id } }" class="book-card-link">
        <div class="book-card d-flex" outlined>
            <v-col cols="12">
                <div class="content-container">
                    <v-img :src="this.$getCoverUrl(book.id)" class="book-cover" height="200" @error="handleImageError"
                        :alt="`封面 - ${book.title}`">
                    </v-img>

                    <div class="book-info">
                        <div class="book-title">{{ book.title }}</div>
                        <div class="book-author">{{ book.author }}</div>
                        <div class="book-meta">
                            <div class="book-language">语言：{{ book.language }}</div>
                            <div class="book-file-type">格式：{{ book.file_type }}</div>
                            <div class="book-file-size">大小：{{ formattedFileSize }}</div>
                        </div>
                    </div>
                </div>
            </v-col>
        </div>
    </router-link>
</template>

  
<script>
export default {
    name: 'BookCard',
    props: {
        book: {
            type: Object,
            required: true
        }
    },
    data() {
        return {
            loadError: false
        };
    },
    computed: {
        formattedFileSize() {
            const fileSizeNum = parseFloat(this.book.file_size); // 使用book对象的file_size属性
            if (!isNaN(fileSizeNum)) {
                if (fileSizeNum >= 1024) {
                    // 文件大小大于或等于 1024MB，转换为 GB
                    return (fileSizeNum / 1024).toFixed(1) + ' GB';
                } else {
                    // 文件大小小于 1024MB，保持 MB 显示
                    return fileSizeNum.toFixed(1) + ' MB';
                }
            }
            return ''; // 如果 file_size 不是数字，则返回空字符串
        }
    },
    methods: {
        handleImageError() {
            this.loadError = true; // 设置标记，表示图片加载失败
        }
    }
};
</script>


<style scoped>
.book-card-link {
    text-decoration: none;
    color: inherit;
}

.book-card {
    display: flex;
    border: 1px solid #ccc;
    transition: box-shadow .3s;
}

.content-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.book-cover {
    max-width: 30%;
    /* Adjust as needed */
    object-fit: cover;
}

.book-info {
    padding-left: 1rem;
    max-width: 65%;
    /* Adjust as needed */
}

.book-title {
    font-size: 1.25rem;
    margin-bottom: 0.25rem;
}

.book-author {
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

.book-meta {
    margin-top: auto;
    /* Pushes the meta information to the bottom */
    font-size: 0.875rem;
}

.book-language,
.book-file-type,
.book-file-size {
    margin-bottom: 0.25rem;
}

.book-card:hover {
    box-shadow: 0 4px 8px rgba(0, 0, 0, .15);
    background-color: rgb(163, 239, 214);
}
</style>
