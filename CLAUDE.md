# solo100 项目说明

设计文档：`docs/superpowers/specs/2026-03-25-solo100-design.md`

---

## 开发规范

### 代码风格
- 后端：Python，遵循 PEP 8，使用类型注解
- 前端：TypeScript，2 空格缩进
- 注释：中文/英文双语

### Git 规范
- commit message 中英文双语，英文在前，格式如下：

```
<type>: <English description>

<中文描述>
```

示例：
```
feat: add Feature state machine executor with retry and rollback support

添加 Feature 状态机驱动逻辑，支持回溯和重试
```

- 不要自动提交，等待用户明确说"提交"或"commit"
- commit message 不加 Co-Authored-By 标签

