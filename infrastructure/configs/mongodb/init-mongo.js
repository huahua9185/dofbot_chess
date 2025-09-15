// MongoDB初始化脚本
// 创建数据库和集合，设置索引

// 切换到象棋机器人数据库
db = db.getSiblingDB('chess_robot');

// 创建用户集合和索引
db.createCollection('users');
db.users.createIndex({ "username": 1 }, { unique: true });
db.users.createIndex({ "email": 1 }, { unique: true });
db.users.createIndex({ "created_at": -1 });

// 创建游戏集合和索引
db.createCollection('games');
db.games.createIndex({ "game_id": 1 }, { unique: true });
db.games.createIndex({ "player_id": 1 });
db.games.createIndex({ "status": 1 });
db.games.createIndex({ "created_at": -1 });
db.games.createIndex({ "updated_at": -1 });

// 创建移动历史集合和索引
db.createCollection('moves');
db.moves.createIndex({ "game_id": 1, "move_number": 1 });
db.moves.createIndex({ "game_id": 1 });
db.moves.createIndex({ "created_at": -1 });

// 创建标定数据集合和索引
db.createCollection('calibration_data');
db.calibration_data.createIndex({ "calibration_type": 1 });
db.calibration_data.createIndex({ "created_at": -1 });
db.calibration_data.createIndex({ "is_active": 1 });

// 创建系统日志集合和索引
db.createCollection('system_logs');
db.system_logs.createIndex({ "service": 1, "timestamp": -1 });
db.system_logs.createIndex({ "level": 1, "timestamp": -1 });
db.system_logs.createIndex({ "timestamp": -1 });

// 创建性能指标集合和索引
db.createCollection('performance_metrics');
db.performance_metrics.createIndex({ "metric_type": 1, "timestamp": -1 });
db.performance_metrics.createIndex({ "service": 1, "timestamp": -1 });
db.performance_metrics.createIndex({ "timestamp": -1 });

// 创建AI分析结果集合和索引
db.createCollection('ai_analysis');
db.ai_analysis.createIndex({ "game_id": 1, "move_number": 1 });
db.ai_analysis.createIndex({ "analysis_type": 1 });
db.ai_analysis.createIndex({ "created_at": -1 });

// 插入初始数据
print('Inserting initial data...');

// 插入默认标定数据
db.calibration_data.insertMany([
    {
        calibration_type: 'camera_intrinsic',
        parameters: {
            camera_matrix: null,
            distortion_coefficients: null,
            image_size: null
        },
        is_active: false,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        calibration_type: 'camera_extrinsic',
        parameters: {
            rotation_matrix: null,
            translation_vector: null,
            homography_matrix: null
        },
        is_active: false,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        calibration_type: 'robot_workspace',
        parameters: {
            workspace_bounds: null,
            joint_limits: null,
            coordinate_transform: null
        },
        is_active: false,
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// 插入系统配置数据
db.createCollection('system_config');
db.system_config.createIndex({ "config_key": 1 }, { unique: true });
db.system_config.insertMany([
    {
        config_key: 'ai_difficulty_default',
        config_value: 3,
        description: 'Default AI difficulty level (1-10)',
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        config_key: 'camera_resolution',
        config_value: { width: 1920, height: 1080 },
        description: 'Default camera resolution',
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        config_key: 'robot_speed_default',
        config_value: 0.5,
        description: 'Default robot movement speed (0.1-1.0)',
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        config_key: 'game_timeout',
        config_value: 1800,
        description: 'Game timeout in seconds (30 minutes)',
        created_at: new Date(),
        updated_at: new Date()
    }
]);

print('MongoDB initialization completed successfully!');
print('Created collections: users, games, moves, calibration_data, system_logs, performance_metrics, ai_analysis, system_config');
print('Created indexes for optimal query performance');
print('Inserted initial configuration and calibration data');