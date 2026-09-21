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
tags: [engineering]
description: "A short summary explaining what readers will learn from this post."
image: ./assets/my_post/banner.png
---
```

- **slug**: URL path for the post (e.g., `/blog/my-post-slug`)
- **authors**: List of author keys defined in `blog/authors.yml`
- **tags**: One or two category keys from the four categories below
- **description**: One concise sentence (roughly 120–200 characters) for the homepage card and social sharing
- **image**: Cover image used on the homepage and for social sharing (Open Graph). Prefer an explicit path to the post banner, rather than a diagram from the article. For posts in `blog/releases/`, use `./../assets/<my_post>/banner.png` so Docusaurus bundles the relative image.

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

### 5. Choose Categories

Use one primary category and, when it adds useful context, one secondary category. Keep the taxonomy limited to these four categories; technology names such as Flink, Iceberg, Rust, or Arrow belong in the title, summary, or article text.

| Key | Label | Use for |
| --- | --- | --- |
| `announcement` | Announcement | Releases, project milestones, and official announcements |
| `case-study` | Case Study | Enterprise case studies and production practices |
| `engineering` | Engineering | Architecture, system internals, and technical deep dives |
| `guides` | Guides | Getting started, how-to guides, application patterns, and best practices |

For example, a graduation announcement uses `[announcement]`; a production tuning deep dive can use `[engineering, guides]`.

### 6. Prepare the Banner

- **Canvas:** 1200 × 510 px (40:17, approximately 2.35:1). A 2400 × 1020 px export is also suitable for high-density screens. Use the same ratio for the featured article and regular cards.
- **Composition:** Keep titles and logos at least 60 px from every edge on the 1200 × 510 canvas. Use a short headline and large type that remain legible at a card width of about 400 px.
- **Export:** Use PNG for text-heavy artwork or WebP/JPEG for photographic images. Aim for a file size below 300 KB where possible.
- **Existing artwork:** The homepage fits the whole image inside the banner frame without stretching or cropping. Images with other ratios have padding. For a full-bleed cover, create a separate banner composed for this canvas and point `image` to it; keep the original illustration in the article body. Simply resizing a 3:2 or square image does not make it 40:17 without distortion or cropping.
- **Missing cover:** The homepage uses the Fluss default cover until a dedicated banner is available. Do not promote a dense technical diagram to a cover just to fill the space.

## Build

```bash
# Production build
npm run build

# Preview the production build locally
npm run serve
```

## Publishing

Once a blog post is merged into the `main` branch, a CI pipeline is automatically triggered to build and publish the latest blog content to the [Apache Fluss website](https://fluss.apache.org/blog).
