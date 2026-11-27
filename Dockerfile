# Ontario School Finder: the prebuilt static site behind nginx.
# deploy.sh packs site/dist into one xz archive (site.tar.xz) so the upload is small and the build context is a
# handful of files. It is unpacked in its own stage with the image's own xzcat (not ADD, whose xz support
# depends on the build server), so the archive never becomes a layer of the final image.
FROM nginx:1.27-alpine AS unpack
COPY site.tar.xz /tmp/site.tar.xz
RUN mkdir /site && xzcat /tmp/site.tar.xz | tar -x -C /site

FROM nginx:1.27-alpine
RUN rm -f /etc/nginx/conf.d/default.conf \
 && printf 'types { application/javascript mjs; application/geo+json geojson; application/manifest+json webmanifest; text/markdown md; text/csv csv; }\n' > /etc/nginx/conf.d/00-types.conf
COPY deploy/nginx.conf /etc/nginx/conf.d/site.conf
COPY deploy/security-headers.conf /etc/nginx/security-headers.conf
COPY --from=unpack /site/ /usr/share/nginx/html/
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/healthz || exit 1
EXPOSE 80
