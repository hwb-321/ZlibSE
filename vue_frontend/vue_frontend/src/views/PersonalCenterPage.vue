<template>
    <div class="personal-center">
        <h1>个人中心</h1>

        <!-- 使用 router-link 直接创建链接 -->
        <router-link to="/uploaded-book-management" class="nav-link">我的上传</router-link>
        <router-link to="/favorites" class="nav-link">收藏夹</router-link>
    </div>
</template>
  
<script>
export default {
    name: 'PersonalCenterPage'
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
  