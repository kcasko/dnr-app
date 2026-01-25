# Template Migration Guide

## Overview

This guide explains how to migrate all existing pages to the new base template system with sidebar navigation.

---

## ✅ Completed Migrations

The following pages have been fully migrated:

1. **Overview** ([overview.html](templates/overview.html)) - Dashboard with actionable alerts
2. **Room Issues** ([room_issues_new.html](templates/room_issues_new.html)) - Management page example
3. **Shift Notes** ([log_book_new.html](templates/log_book_new.html)) - Two-column layout example

---

## 📋 Remaining Pages to Migrate

| Priority | Page | File | Complexity | Notes |
|----------|------|------|------------|-------|
| HIGH | DNR List | index.html | COMPLEX | Has modals, JavaScript, photo upload |
| HIGH | Maintenance | maintenance.html | MEDIUM | Similar to room_issues |
| HIGH | Housekeeping | housekeeping_requests.html | COMPLEX | Dual-column,TODAY sidebar |
| MED | Staff Announcements | staff_announcements.html | SIMPLE | Standard management page |
| MED | In-House Messages | in_house_messages.html | SIMPLE | Standard management page |
| LOW | Important Numbers | important_numbers.html | SIMPLE | Reference page |
| LOW | How-To Guides | how_to_guides.html | SIMPLE | Reference with file upload |
| LOW | Food & Local Spots | food_local_spots.html | SIMPLE | Reference page |
| LOW | Cleaning Checklists | cleaning_checklists.html | SIMPLE | Read-only reference |
| LOW | Settings | settings.html | SIMPLE | Standalone settings |

---

## 🎯 Migration Template

### Standard Management Page Pattern

Use this for: Maintenance, Staff Announcements, In-House Messages, Important Numbers, How-To Guides, Food & Local

```jinja2
{% extends "base.html" %}

{% block title %}Page Name{% endblock %}

{% block page_title %}Page Name{% endblock %}

{% block page_subtitle %}
<p class="page-subtitle">Brief description of what this page does</p>
{% endblock %}

{% block page_actions %}
<button type="button" class="btn btn-primary" onclick="scrollToForm()">+ Add Item</button>
{% endblock %}

{% block content %}

<!-- Optional: Filters/Toolbar -->
{% if has_filters %}
<div class="toolbar-section">
    <div class="filter-buttons">
        <a href="/page?filter=active" class="filter-btn active">Active</a>
        <a href="/page?filter=all" class="filter-btn">All</a>
    </div>
</div>
{% endif %}

<!-- List of Items -->
<div class="management-section">
    {% if items %}
        {% for item in items %}
        <div class="management-card">
            <div class="card-header">
                <div>
                    <div class="card-title">{{ item.title }}</div>
                    <div class="card-meta">Created: {{ item.created_at }}</div>
                </div>
                <div class="card-badges">
                    <span class="status-badge {{ item.status }}">{{ item.status }}</span>
                </div>
            </div>
            {% if item.description %}
            <div class="card-content text-pre-wrap">{{ item.description }}</div>
            {% endif %}
            <div class="card-actions">
                <a href="/page?edit={{ item.id }}" class="btn btn-secondary">Edit</a>
                <form method="POST" action="/page/{{ item.id }}/delete" class="inline-form">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
                    <button type="submit" class="btn btn-danger"
                        onclick="return confirm('Delete this item?')">Delete</button>
                </form>
            </div>
        </div>
        {% endfor %}
    {% else %}
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <h3>No items found</h3>
            <p>Click "+ Add Item" above to create one.</p>
        </div>
    {% endif %}
</div>

<!-- Add Form -->
<div class="management-form-section" id="form-section">
    <h2 class="form-section-title">{% if editing %}Edit Item{% else %}Add Item{% endif %}</h2>
    <form method="POST" action="/page">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <div class="form-group">
            <label for="title">Title *</label>
            <input type="text" id="title" name="title" required>
        </div>
        <div class="form-group">
            <label for="description">Description</label>
            <textarea id="description" name="description"></textarea>
        </div>
        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
        </div>
    </form>
</div>

{% endblock %}

{% block extra_js %}
<script>
function scrollToForm() {
    document.getElementById('form-section').scrollIntoView({ behavior: 'smooth' });
}
</script>
{% endblock %}
```

---

### Two-Column Layout Pattern

Use this for: Pages that need a persistent form/sidebar (like Shift Notes was)

```jinja2
{% extends "base.html" %}

{% block content %}

<div class="two-column-layout">
    <!-- Left: Main Content -->
    <div class="feed-column">
        <h2>Items</h2>
        {% for item in items %}
        <!-- Item display -->
        {% endfor %}
    </div>

    <!-- Right: Actions/Forms -->
    <div class="sidebar-column">
        <div class="sticky-container">
            <div class="form-card">
                <h2>Add New</h2>
                <form>...</form>
            </div>
        </div>
    </div>
</div>

{% endblock %}

{% block extra_css %}
<style>
.two-column-layout {
    display: grid;
    grid-template-columns: 1fr 400px;
    gap: 24px;
}
.sticky-container {
    position: sticky;
    top: 90px;
}
</style>
{% endblock %}
```

---

## 🔧 Step-by-Step Migration Process

### 1. Create New File

```bash
# Don't overwrite original yet - create _new.html version
cp templates/page.html templates/page_new.html
```

### 2. Replace Header Section

**Remove:**
```html
<header>
    <div class="header-content">
        <img src="/static/sleep_inn_logo.png" ...>
        <div class="header-text">
            <h1>Page Title</h1>
        </div>
        <div class="header-actions">
            <a href="/overview" ...>Overview</a>
            <!-- 8+ navigation links -->
        </div>
    </div>
</header>
```

**Replace with:**
```jinja2
{% extends "base.html" %}

{% block title %}Page Title{% endblock %}
{% block page_title %}Page Title{% endblock %}
{% block page_subtitle %}
<p class="page-subtitle">Description</p>
{% endblock %}
```

### 3. Move Primary Action to page_actions Block

**Remove from content area:**
```html
<button class="btn-add">+ Add Thing</button>
```

**Move to:**
```jinja2
{% block page_actions %}
<button class="btn btn-primary">+ Add Thing</button>
{% endblock %}
```

### 4. Wrap Content

**Remove:**
```html
<div class="container">
    <!-- content -->
</div>
```

**Replace with:**
```jinja2
{% block content %}
<!-- content goes here, no container div needed -->
{% endblock %}
```

### 5. Remove Footer

Delete the entire footer section - it's now in base.html.

### 6. Move Inline Styles to extra_css Block

```jinja2
{% block extra_css %}
<style>
/* Page-specific styles */
</style>
{% endblock %}
```

### 7. Move Inline Scripts to extra_js Block

```jinja2
{% block extra_js %}
<script>
// Page-specific JavaScript
</script>
{% endblock %}
```

---

## 🎨 CSS Classes Reference

### Card System

```html
<!-- Management Cards (for lists of items) -->
<div class="management-card">
    <div class="card-header">...</div>
    <div class="card-content">...</div>
    <div class="card-actions">...</div>
</div>

<!-- Form Cards (for forms in sidebar) -->
<div class="form-card">
    <h2>Form Title</h2>
    <form>...</form>
</div>
```

### Button Hierarchy

```html
<!-- Primary (blue, filled) -->
<button class="btn btn-primary">Add Item</button>

<!-- Secondary (outlined) -->
<button class="btn btn-secondary">Edit</button>

<!-- Destructive (red) -->
<button class="btn btn-danger">Delete</button>

<!-- Link (text-only) -->
<a href="#" class="btn-link">View More →</a>
```

### Empty States

```html
<div class="empty-state">
    <div class="empty-state-icon">📭</div>
    <h3>No items found</h3>
    <p>Helpful message for the user</p>
</div>
```

---

## ⚠️ Common Pitfalls

### 1. Forgetting to Remove Old Container Div

❌ **Wrong:**
```jinja2
{% block content %}
<div class="container">  <!-- This creates double containers! -->
    ...
</div>
{% endblock %}
```

✅ **Correct:**
```jinja2
{% block content %}
    <!-- No container div - base.html handles spacing -->
    <div class="management-section">...</div>
{% endblock %}
```

### 2. Using Old Header Classes

❌ **Wrong:**
```html
<div class="header-actions">
    <button class="logout-btn">Add</button>
</div>
```

✅ **Correct:**
```jinja2
{% block page_actions %}
<button class="btn btn-primary">+ Add</button>
{% endblock %}
```

### 3. Sidebar Active State

The base template automatically highlights the active sidebar link based on `request.path`. Make sure your routes match the sidebar hrefs exactly:

```python
# Sidebar has: href="/maintenance"
# Route should be:
@app.route('/maintenance')  # ✅ Matches
# NOT:
@app.route('/maintenance/')  # ❌ Won't highlight
```

---

## 🚀 Testing Checklist

After migrating each page:

- [ ] Page loads without errors
- [ ] Sidebar shows active state on correct link
- [ ] Page title displays correctly
- [ ] Page subtitle displays correctly
- [ ] Primary action button appears in top-right
- [ ] All forms still submit correctly
- [ ] All delete confirmations still work
- [ ] Empty states display correctly
- [ ] Responsive layout works on mobile (sidebar collapses)
- [ ] No console errors
- [ ] CSS doesn't conflict with base styles

---

## 📦 Deployment Steps

Once all *_new.html files are tested:

```bash
# Backup originals
mv templates/page.html templates/page_old.html

# Rename new files
mv templates/page_new.html templates/page.html

# Test in production
# If issues found, restore:
# mv templates/page_old.html templates/page.html
```

---

## 🎯 Quick Reference: File Checklist

- [ ] overview.html ✅ DONE
- [ ] room_issues.html ✅ DONE (as room_issues_new.html)
- [ ] log_book.html ✅ DONE (as log_book_new.html)
- [ ] index.html (DNR) ⏳ TODO
- [ ] maintenance.html ⏳ TODO
- [ ] housekeeping_requests.html ⏳ TODO
- [ ] staff_announcements.html ⏳ TODO
- [ ] in_house_messages.html ⏳ TODO
- [ ] important_numbers.html ⏳ TODO
- [ ] how_to_guides.html ⏳ TODO
- [ ] food_local_spots.html ⏳ TODO
- [ ] cleaning_checklists.html ⏳ TODO
- [ ] settings.html ⏳ TODO

---

## 💡 Tips

1. **Migrate one page at a time** - Test thoroughly before moving to the next
2. **Start with simple pages** - Important Numbers, Food & Local are easiest
3. **Save DNR for last** - It's the most complex with modals and JavaScript
4. **Keep _new.html suffix** until fully tested
5. **Use browser DevTools** to check for CSS conflicts

---

## Need Help?

If a page doesn't fit these patterns:
1. Check if it needs a custom layout (reference [room_issues_new.html](templates/room_issues_new.html) or [log_book_new.html](templates/log_book_new.html))
2. Copy the closest existing pattern
3. Adjust only what's necessary for that page's unique needs

The goal is **consistency**, not perfection. Every page should feel like part of the same app.
