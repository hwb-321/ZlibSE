<template>
    <v-card class="book-card-with-delete">
        <v-card-text>
            <BookCard :book="book" />
        </v-card-text>
        <v-card-actions class="delete-button-container">
            <v-btn color="error" variant="outlined" class="delete-btn" @click="deleteBook(book.id)">删除</v-btn>
        </v-card-actions>
    </v-card>
</template>
  
<script>
import BookCard from './BookCard.vue'; // 假设 BookCard 在同一目录下\
import axios from 'axios';
import appConfig from '@/config/appConfig.json';

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
                const response = await axios.delete(`${appConfig.backendUrl}/api/users/me/uploads/${bookId}`);
                if (response.data.success) {
                    this.$emit('bookDeleted', bookId);
                }
            } catch (error) {
                console.error('删除书籍时发生错误:', error);
            }
        },
    }
};
</script>
  
<style scoped>
.book-card-with-delete {
    display: flex;
    flex-direction: column;
}

.delete-button-container {
    display: flex;
    justify-content: center;
}

.delete-btn {
    font-size: 17px;
    /* 设置字体大小为 17px */
}
</style>
