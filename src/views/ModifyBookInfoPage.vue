<template>
    <v-container>
        <v-row>
            <v-col cols="12" class="d-flex justify-space-around align-center mb-3">
                <h1>书籍不可编辑</h1>
                <router-link to="/uploaded-book-management">
                    <v-btn color="secondary">返回上传管理</v-btn>
                </router-link>
            </v-col>
        </v-row>

        <v-alert type="warning" variant="tonal" class="mb-4">
            后端已取消“修改书籍信息”接口。当前书籍创建后不能再修改，如果要更换正文、封面或元数据，请先删除这本书，再重新上传创建。
        </v-alert>

        <v-card variant="outlined">
            <v-card-text>
                <p class="mb-3">当前后端规则：</p>
                <ul>
                    <li>正文文件先上传并解析，解析完成后再创建书籍。</li>
                    <li>书籍创建成功后只支持删除，不支持编辑。</li>
                    <li>如需修改，请回到上传管理删除后重新上传。</li>
                </ul>
            </v-card-text>
        </v-card>
    </v-container>
</template>

<script>
export default {
    mounted() {
        this.$nextTick(() => {
            document.title = '书籍不可编辑';
        });
    },
};
</script>
