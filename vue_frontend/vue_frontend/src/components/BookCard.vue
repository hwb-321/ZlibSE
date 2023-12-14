<template>
    <router-link :to="{ name: 'BookDetail', params: { id: book.id } }" class="book-card-link">
        <div class="book-card">
            <img v-if="!loadError" :src="this.$getCoverUrl(book.id)" alt="封面" class="book-cover"
                @error="handleImageError">
            <h3>{{ book.title }}</h3>
            <p>作者：{{ book.author }}</p>
            <p>id: {{ book.id }}</p>
            <!-- 可以添加其他书籍信息 -->
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
    /* 移除链接下划线 */
    color: inherit;
    /* 使用继承的文字颜色 */
}

.book-card {
    border: 1px solid #ccc;
    padding: 10px;
    margin-bottom: 10px;
    display: block;
    /* 使 div 行为像链接 */
    cursor: pointer;
    /* 鼠标悬停时显示手形光标 */
}

.book-cover {
    max-width: 100%;
    max-height: 200px;
    width: auto;
    height: auto;
    margin-bottom: 10px;
    object-fit: contain;
}
</style>
