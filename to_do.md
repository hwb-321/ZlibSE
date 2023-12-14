## 获取书籍总数
- **URL**: `/book/count`
- **Method**: `GET`
- **Description**: 返回数据库中书籍的总数。

## 获取书籍列表
- **URL**: `/book/list?page=1&pageSize=10`
- **Method**: `GET`
- **Description**: 返回分页的书籍列表。
- **Query Parameters**:
  - `page` (optional): 请求的页码。默认为1。
  - `pageSize` (optional): 每页显示的书籍数量。默认为10。
- **Default Behavior**: 如果未提供`page`和`pageSize`参数，接口默认返回第1页，每页10本书籍的列表。

## 获取指定书籍的详细信息
- **URL**: `/book/get_descriptions/{book_id}`
- **Method**: `GET`
- **Description**: 根据书籍ID获取具体的书籍信息。

## 搜索书籍
- **URL**: `/book/search?query=xxx`
- **Method**: `GET`
- **Description**: 根据提供的查询字符串搜索书籍。返回包含查询字符串的书籍列表。会搜索书名、作者、ISBN。

## 下载书籍
- **URL**: `/book/download/{book_id}`
- **Method**: `GET`
- **Description**: 根据书籍ID下载书籍。

## 上传书籍
- **URL**: `/book/upload_book`
- **Method**: `POST`
- **Description**: 上传新的书籍。支持上传书籍信息和文件。

## 获取封面
- **URL**: `/book/cover/{book_id}`
- **Method**: `GET`
- **Description**: 根据书籍ID获取封面图片。