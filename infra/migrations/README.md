# 数据库迁移

`001_control_plane.sql` 是第一周控制面基础迁移，适用于空库和已有本地开发库。

生产环境执行迁移前必须：

1. 由发布流水线获取 migration lock。
2. 在备份或快照后执行。
3. 验证索引、唯一约束和行数。
4. 记录 migration revision，并在应用启动时拒绝未知版本。

本地开发可以使用 PostgreSQL 容器中的 `psql` 执行该文件；应用的 `AUTO_CREATE_SCHEMA=true` 只用于本地快速启动，不作为生产迁移方案。

