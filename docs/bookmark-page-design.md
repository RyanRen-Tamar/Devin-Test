# 收藏夹页面设计方案 (Bookmark Page Design)

## 1. 布局结构 (Layout Structure)

### 左侧边栏 (Left Sidebar)
- 保持现有的日历月视图
- 添加"我的收藏"导航项（突出显示）
- 保持团队/用户头像区域

### 主要内容区域 (Main Content Area)
- 顶部标题栏："我的收藏"
- 分类筛选栏
  - 按时间排序
  - 按类型筛选
  - 搜索框

### 收藏列表视图 (Bookmark List View)
- 网格布局展示（3列）
- 每个收藏项包含：
  - 任务卡片预览
  - 创建日期
  - 模板状态标识
  - 操作按钮（...）

## 2. 交互设计 (Interaction Design)

### 收藏操作 (Bookmark Actions)
- 点击收藏项展开详情
- 右键菜单或更多按钮（...）显示操作选项：
  - 存储为模板
  - 编辑
  - 删除
  - 分享

### 模板创建流程 (Template Creation Flow)
1. 点击收藏项的更多按钮（...）
2. 选择"存储为模板"选项
3. 弹出模板设置对话框：
   - 模板名称
   - 描述
   - 可重用字段设置
4. 确认创建

## 3. 视觉设计 (Visual Design)

### 配色方案 (Color Scheme)
- 延续主界面配色：
  - 背景色：浅灰/米色 (#F5F5F4)
  - 强调色：青色 (#2DD4BF)
  - 文字：黑色（主要）、灰色（次要）

### 卡片设计 (Card Design)
- 圆角矩形（border-radius: 12px）
- 轻微阴影效果
- 悬停效果：阴影加深
- 状态标识：
  - 普通收藏：灰色标签
  - 已设为模板：青色标签

### 图标系统 (Icon System)
- 使用 Lucide React 图标库
- 收藏星标：<Star />
- 模板图标：<Template />
- 更多操作：<MoreVertical />
- 编辑：<Edit />
- 删除：<Trash />

## 4. 组件设计 (Component Design)

### BookmarkCard 组件
```typescript
interface BookmarkCard {
  id: string;
  title: string;
  description: string;
  createdAt: Date;
  isTemplate: boolean;
  tags: string[];
  color: string;
}
```

### TemplateDialog 组件
```typescript
interface TemplateDialog {
  isOpen: boolean;
  onClose: () => void;
  bookmarkData: BookmarkCard;
  onSave: (templateData: TemplateData) => void;
}
```

## 5. 功能特性 (Features)

### 基础功能 (Basic Features)
- 收藏项展示
- 模板转换
- 搜索筛选
- 排序功能

### 高级功能 (Advanced Features)
- 批量操作
- 拖拽排序
- 分享功能
- 导出功能

## 6. 交互反馈 (Interaction Feedback)
- 操作成功提示（使用 Toast 组件）
- 加载状态指示（使用 Skeleton 组件）
- 错误提示
- 确认对话框

## 7. 性能优化 (Performance Optimization)
- 虚拟滚动（大量收藏项时）
- 图片懒加载
- 分页加载（每页20项）
- 本地缓存常用模板
