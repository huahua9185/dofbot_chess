// MongoDB认证数据库初始化脚本
// 创建认证专用数据库和用户

// 切换到认证数据库
db = db.getSiblingDB('chess_robot_auth');

// 创建认证用户
db.createUser({
    user: 'auth_user',
    pwd: 'auth_pass_2024',
    roles: [
        {
            role: 'readWrite',
            db: 'chess_robot_auth'
        }
    ]
});

// 创建集合和索引
db.createCollection('users');
db.createCollection('roles');
db.createCollection('permissions');
db.createCollection('sessions');

// 用户集合索引
db.users.createIndex({ "username": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "status": 1 });
db.users.createIndex({ "last_login": 1 });
db.users.createIndex({ "created_at": 1 });

// 角色集合索引
db.roles.createIndex({ "name": 1 }, { unique: true });
db.roles.createIndex({ "is_system": 1 });

// 权限集合索引
db.permissions.createIndex({ "name": 1 }, { unique: true });
db.permissions.createIndex({ "resource": 1, "action": 1 });

// 会话集合索引
db.sessions.createIndex({ "session_id": 1 }, { unique: true });
db.sessions.createIndex({ "username": 1 });
db.sessions.createIndex({ "expires_at": 1 });
db.sessions.createIndex({ "is_active": 1 });

print('Chess Robot认证数据库初始化完成');

// 打印创建的集合
print('创建的集合:');
db.runCommand("listCollections").cursor.firstBatch.forEach(
    function(collection) {
        print(' - ' + collection.name);
    }
);