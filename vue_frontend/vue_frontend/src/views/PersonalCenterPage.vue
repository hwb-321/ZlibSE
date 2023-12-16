<template>
    <div class="personal-center">
        <v-row class="mb-3">
            <v-col cols="12" md="8" class="d-flex justify-start align-center">
                <h1>个人中心</h1>
            </v-col>
            <v-col cols="12" md="4" class="d-flex justify-end align-center">
                <router-link to="/home">
                    <v-btn color="secondary">返回主界面</v-btn>
                </router-link>
            </v-col>
        </v-row>

        <router-link to="/uploaded-book-management" class="nav-link">我的上传</router-link>
        <router-link to="/favorites" class="nav-link">收藏夹</router-link>
        <router-link to="/change-password" class="nav-link">修改密码</router-link>
    </div>
</template>
  
  
<script>
export default {
    name: 'PersonalCenterPage',
    mounted() {
        this.$nextTick(() => {
            document.title = '个人中心';
        });
    },
};
</script>
  
<style scoped>
.personal-center {
    margin: 20px;
}

.nav-link {
    display: block;
    margin-bottom: 10px;
    padding: 10px;
    background-color: #0056b3;
    color: white;
    text-align: center;
    border-radius: 5px;
    text-decoration: none;
}
</style>