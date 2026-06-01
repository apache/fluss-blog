import React from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import {useBlogPost} from '@docusaurus/plugin-content-blog/client';
import styles from './styles.module.css';

type Props = {
  className?: string;
};

export default function BlogPostItemHeaderTitle({className}: Props): JSX.Element {
  const {metadata, isBlogPostPage} = useBlogPost();
  const {permalink, title, frontMatter} = metadata;
  const subtitle = (frontMatter as {subtitle?: string}).subtitle;
  const TitleHeading = isBlogPostPage ? 'h1' : 'h2';

  return (
    <>
      <TitleHeading className={clsx(styles.title, className)} itemProp="headline">
        {isBlogPostPage ? title : <Link to={permalink} itemProp="url">{title}</Link>}
      </TitleHeading>
      {subtitle && (
        <p className={clsx(styles.subtitle, 'blog-post-subtitle')}>{subtitle}</p>
      )}
    </>
  );
}
