<template>
    <router-link :to="{ name: 'BookDetail', params: { bookId: book.id } }" class="book-card-link">
        <div class="book-card d-flex" outlined>
            <v-col cols="12">
                <div class="content-container">
                    <v-img :src="coverUrl" class="book-cover" height="200" @error="handleImageError"
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
            required: true,
        },
    },
    data() {
        return {
            loadError: false,
            coverUrl: '',
        };
    },
    computed: {
        formattedFileSize() {
            const fileSizeNum = parseFloat(this.book.file_size);
            if (!Number.isNaN(fileSizeNum)) {
                if (fileSizeNum >= 1024) {
                    return `${(fileSizeNum / 1024).toFixed(1)} GB`;
                }
                return `${fileSizeNum.toFixed(1)} MB`;
            }
            return '';
        },
    },
    watch: {
        'book.cover_image_path': {
            immediate: true,
            handler() {
                this.loadCoverUrl();
            },
        },
    },
    methods: {
        async loadCoverUrl() {
            if (this.loadError || !this.book.cover_image_path) {
                this.coverUrl = '';
                return;
            }
            try {
                this.coverUrl = await this.$getCoverUrl(this.book.cover_image_path);
            } catch (error) {
                console.error('加载封面地址失败:', error);
                this.coverUrl = '';
            }
        },
        handleImageError() {
            this.loadError = true;
            this.coverUrl = '';
        },
    },
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
    object-fit: cover;
}

.book-info {
    padding-left: 1rem;
    max-width: 65%;
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
