<template>
    <div class="book-card-with-delete">
        <BookCard :book="book" />
        <button @click="deleteBook(book.id)" class="delete-btn">删除</button>
    </div>
</template>
  
<script>
import BookCard from './BookCard.vue'; // 假设 BookCard 在同一目录下\
import axios from 'axios';

export default {
    components: {
        BookCard
    },
    props: {
        book: {
            type: Object,
            required: true
        }
    },
    methods: {
        async deleteBook(bookId) {
            try {
                const response = await axios.post(`${process.env.VUE_APP_BACKEND_URL}/user/delete_uploaded_book/${bookId}`, {}, { withCredentials: true });
                if (response.data.success) {
                    this.$emit('bookDeleted', bookId);
                }
            } catch (error) {
                console.error('删除书籍时发生错误:', error);
            }
        }
    }
};
</script>
  
<style scoped>
.book-card-with-delete {
    display: flex;
    align-items: center;
}

.delete-btn {
    margin-left: 10px;
    /* 按钮样式，可根据需要调整 */
}
</style>
  