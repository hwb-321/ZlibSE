<template>
    <div class="main-container" ref="mainContainer">
        <button class="nav-button" id="prev" @click="prevPage">‹</button>
        <div class="book" ref="book"></div>
        <button class="nav-button" id="next" @click="nextPage">›</button>
        <button class="toc-button" id="tocBtn" @click="toggleToc">目录</button>
        <div class="toc" v-if="tocVisible" ref="toc">
            <a v-for="item in toc" :key="item.id" :href="item.href" @click.prevent="goToSection(item.href)">
                {{ item.label }}
            </a>
        </div>
    </div>
</template>
  
<script>
import ePub from 'epubjs';

export default {
    data() {
        return {
            book: null,
            rendition: null,
            toc: [],
            tocVisible: false,
        };
    },
    mounted() {
        this.$nextTick(() => {
            document.title = '在线阅读';
        });

        const bookId = this.$route.query.bookId;
        const bookUrl = `${process.env.VUE_APP_BACKEND_URL}/book/download/${bookId}.epub`;
        this.book = ePub(bookUrl);
        this.rendition = this.book.renderTo(this.$refs.book, { width: '100%', height: '100%' });
        this.rendition.display();

        this.book.loaded.navigation.then((navigation) => {
            this.toc = navigation.toc;
        });
    },
    methods: {
        toggleToc() {
            this.tocVisible = !this.tocVisible;
        },
        prevPage() {
            this.rendition.prev();
        },
        nextPage() {
            this.rendition.next();
        },
        goToSection(href) {
            this.rendition.display(href);
            this.tocVisible = false;
        },
    },
};
</script>
  
<style>
.main-container {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
}

.book {
    width: 100%;
    height: calc(100vh - 60px);
    text-align: justify;
    padding: 10px 60px;
    box-sizing: border-box;
}

.nav-button {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    background-color: #333;
    border: none;
    padding: 10px;
    cursor: pointer;
    color: #fff;
    font-size: 1.5em;
    z-index: 100;
}

#prev {
    left: 10px;
}

#next {
    right: 10px;
}

.toc-button {
    position: fixed;
    top: 10px;
    left: 10px;
    background-color: #333;
    color: #fff;
    padding: 5px 10px;
    border: none;
    cursor: pointer;
    font-size: 1.2em;
    z-index: 101;
}

.toc {
    position: fixed;
    left: 0;
    top: 50px;
    width: 250px;
    height: calc(100vh - 50px);
    background: #222;
    overflow-y: auto;
    padding: 10px;
    display: block;
    z-index: 100;
}

.toc a {
    color: #ddd;
    text-decoration: none;
    display: block;
    padding: 5px;
}

.toc a:hover {
    background-color: #333;
}
</style>
  