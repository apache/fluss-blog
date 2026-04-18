# Apache Fluss Blog

This repository contains the source for the [Apache Fluss (Incubating)](https://fluss.apache.org/) blog, built with [Docusaurus 3](https://docusaurus.io/).

## Project Structure

```
├── blog/                    # Blog content
│   ├── YYYY-MM-DD-slug.md   # Blog posts (Markdown/MDX)
│   ├── assets/              # Post-specific images and media
│   ├── releases/            # Release announcement posts
│   ├── static/              # Blog-related static files (avatars)
│   ├── authors.yml          # Author profiles
│   └── tags.yml             # Tag definitions
├── static/                  # Global static assets (logo, favicon)
│   └── img/
├── src/css/                 # Custom CSS
├── docusaurus.config.ts     # Site configuration
└── package.json
```

## Local Development

```bash
# Install dependencies
npm install

# Start the dev server (with hot reload)
npm run start
```

The site will be available at `http://localhost:3000`.

## How to Add a Blog Post

### 1. Create a Markdown File

Add a new file under `blog/` with the naming convention:

```
blog/YYYY-MM-DD-my-post-slug.md
```

### 2. Add Frontmatter

Every post must start with YAML frontmatter:

```yaml
---
slug: my-post-slug
title: "My Blog Post Title"
date: YYYY-MM-DD
authors: [jark]
tags: [apache-fluss]
image: ./assets/my_post/banner.png
---
```

- **slug**: URL path for the post (e.g., `/blog/my-post-slug`)
- **authors**: List of author keys defined in `blog/authors.yml`
- **tags**: List of tag keys defined in `blog/tags.yml`
- **image**: (Optional) Cover image used for social sharing (Open Graph)

### 3. Add Images

Place post-specific images in `blog/assets/<post_name>/` and reference them with relative paths:

```markdown
![My Diagram](assets/my_post/diagram.png)
```

### 4. Add Yourself as an Author

If you're a new author, add an entry to `blog/authors.yml`:

```yaml
your_key:
  name: Your Name
  title: Your Title
  url: https://github.com/your-github
  image_url: /avatars/your-avatar.png
```

Then place your avatar image in `blog/static/avatars/`.

### 5. Register New Tags

If your post uses a new tag, define it in `blog/tags.yml`:

```yaml
my-new-tag:
  label: 'My New Tag'
```

## Build

```bash
# Production build
npm run build

# Preview the production build locally
npm run serve
```

## Publishing

Once a blog post is merged into the `main` branch, a CI pipeline is automatically triggered to build and publish the latest blog content to the [Apache Fluss website](https://fluss.apache.org/blog).
