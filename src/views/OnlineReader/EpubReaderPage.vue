<template>
    <div class="main-container" ref="mainContainer">
        <div v-if="!readerReady" class="loading-panel">
            <div class="loading-title">正在准备在线阅读</div>
            <v-progress-linear
                :model-value="downloadProgress"
                color="primary"
                height="18"
                rounded
            ></v-progress-linear>
            <div class="loading-text">{{ progressText }}</div>
            <div v-if="errorMessage" class="reader-error">{{ errorMessage }}</div>
        </div>

        <button class="nav-button" id="prev" @click="prevPage" :disabled="!readerReady">‹</button>
        <div class="book" ref="book"></div>
        <button class="nav-button" id="next" @click="nextPage" :disabled="!readerReady">›</button>
        <button class="toc-button" id="tocBtn" @click="toggleToc" :disabled="!readerReady">目录</button>
        <div class="toc" v-if="tocVisible" ref="toc">
            <a v-for="item in toc" :key="item.id" :href="item.href" @click.prevent="goToSection(item.href)">
                {{ item.label }}
            </a>
        </div>
    </div>
</template>

<script>
import axios from 'axios';
import ePub from 'epubjs';
import appConfig from '@/config/appConfig.json';

export default {
    data() {
        return {
            book: null,
            rendition: null,
            bookUrl: '',
            toc: [],
            tocVisible: false,
            readerReady: false,
            errorMessage: '',
            downloadProgress: 0,
            loadingStage: '正在下载文件...',
        };
    },
    computed: {
        progressText() {
            if (this.errorMessage) {
                return '加载失败';
            }
            if (this.readerReady) {
                return '加载完成';
            }
            return `${this.loadingStage} ${this.downloadProgress}%`;
        },
    },
    async mounted() {
        this.$nextTick(() => {
            document.title = '在线阅读';
        });

        try {
            let fileId = this.$route.query.fileId;
            if (!fileId) {
                const bookId = this.$route.query.bookId;
                const response = await axios.get(`${appConfig.backendUrl}/book/get_descriptions/${bookId}`);
                fileId = response.data.book_file_id;
            }

            const response = await axios.get(
                `${appConfig.backendUrl}/api/files/${fileId}/content`,
                {
                    params: { download: false },
                    responseType: 'arraybuffer',
                    onDownloadProgress: (event) => {
                        if (event.total) {
                            this.downloadProgress = Math.min(100, Math.round((event.loaded / event.total) * 100));
                        } else if (event.loaded > 0) {
                            this.downloadProgress = Math.min(95, this.downloadProgress + 5);
                        }
                    },
                },
            );

            this.downloadProgress = 100;
            this.loadingStage = '正在初始化阅读器...';
            const epubBlob = new Blob([response.data], {
                type: 'application/epub+zip',
            });
            this.bookUrl = URL.createObjectURL(epubBlob);
            this.book = ePub(this.bookUrl);
            this.rendition = this.book.renderTo(this.$refs.book, { width: '100%', height: '100%' });
            await this.rendition.display();

            this.book.loaded.navigation.then((navigation) => {
                this.toc = navigation.toc;
            });
            this.readerReady = true;
        } catch (error) {
            console.error('加载在线阅读内容失败:', error);
            this.errorMessage = '在线阅读加载失败，请返回详情页后重试';
            this.readerReady = false;
        }
    },
    beforeUnmount() {
        if (this.book?.destroy) {
            this.book.destroy();
        }
        if (this.bookUrl) {
            URL.revokeObjectURL(this.bookUrl);
        }
    },
    methods: {
        toggleToc() {
            if (!this.readerReady) {
                return;
            }
            this.tocVisible = !this.tocVisible;
        },
        prevPage() {
            if (!this.readerReady || !this.rendition) {
                return;
            }
            this.rendition.prev();
        },
        nextPage() {
            if (!this.readerReady || !this.rendition) {
                return;
            }
            this.rendition.next();
        },
        goToSection(href) {
            if (!this.readerReady || !this.rendition) {
                return;
            }
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

.loading-panel {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: min(520px, 82vw);
    padding: 24px;
    background: rgba(20, 20, 24, 0.94);
    color: #fff;
    border-radius: 16px;
    z-index: 130;
}

.loading-title {
    font-size: 20px;
    margin-bottom: 16px;
    text-align: center;
}

.loading-text {
    margin-top: 12px;
    text-align: center;
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

.nav-button:disabled,
.toc-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
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

.reader-error {
    margin-top: 14px;
    text-align: center;
    color: #ffb3b3;
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
