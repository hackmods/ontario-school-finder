# Ontario School Finder: the prebuilt static site behind nginx.
# deploy.sh packs site/dist into one archive (site.tar.gz) so the build context is a handful of files.
FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf \
 && printf 'types { application/javascript mjs; application/geo+json geojson; application/manifest+json webmanifest; text/markdown md; text/csv csv; }\n' > /etc/nginx/conf.d/00-types.conf
COPY deploy/nginx.conf /etc/nginx/conf.d/site.conf
COPY deploy/security-headers.conf /etc/nginx/security-headers.conf
ADD site.tar.gz /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
EXPOSE 80
