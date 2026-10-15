FROM node:24-alpine@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS frontend
WORKDIR /frontend
COPY web/package.json web/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY web/scene.js web/terrain3d.js web/terrain-workspace.js web/site-geometry.js web/hydraulic.js web/hybrid.js web/hybrid-model.js web/build.mjs ./
RUN npm run build

FROM deltares/sfincs-cpu@sha256:4301bffc74f3cb3f334be5d21aa75dfe5742a16c9838942cdfc2f870859fb404 AS solver

FROM mambaorg/micromamba@sha256:e0a99b0f17a759e14c2f967dc0ca2d3a3c1ca3c62955f4d20bba770eaaf0184d
COPY --chown=$MAMBA_USER:$MAMBA_USER locks /tmp/locks
RUN micromamba install -y -n base --file /tmp/locks/conda-linux-64.lock && micromamba clean --all --yes
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip install --no-deps -r /tmp/locks/pip-linux-64.lock && python -m pip check
# Authoritative LINZ NZGeoid2016 grid distributed by PROJ-data, CC BY 4.0.
RUN python -c "import urllib.request,hashlib,pathlib; b=urllib.request.urlopen('https://cdn.proj.org/nz_linz_nzgeoid2016.tif',timeout=90).read(); assert hashlib.sha256(b).hexdigest()=='b986261d778e30b52b7d9ae24280c704c280c13bb02e51f3dca65fa862d1f027'; pathlib.Path('/opt/conda/share/proj/nz_linz_nzgeoid2016.tif').write_bytes(b)"
WORKDIR /work
COPY --chown=$MAMBA_USER:$MAMBA_USER pyproject.toml /work/
COPY --chown=$MAMBA_USER:$MAMBA_USER src /work/src
COPY --chown=$MAMBA_USER:$MAMBA_USER web /work/web
COPY --from=frontend --chown=$MAMBA_USER:$MAMBA_USER /frontend/node_modules /work/web/node_modules
COPY --from=frontend --chown=$MAMBA_USER:$MAMBA_USER /frontend/scene.bundle.js /work/web/scene.bundle.js
COPY --from=frontend --chown=$MAMBA_USER:$MAMBA_USER /frontend/terrain3d.bundle.js /work/web/terrain3d.bundle.js
COPY --from=frontend --chown=$MAMBA_USER:$MAMBA_USER /frontend/hybrid.bundle.js /work/web/hybrid.bundle.js
COPY --chown=$MAMBA_USER:$MAMBA_USER scripts /work/scripts
COPY --chown=$MAMBA_USER:$MAMBA_USER docs /work/docs
COPY --chown=$MAMBA_USER:$MAMBA_USER tests /work/tests
COPY --chown=$MAMBA_USER:$MAMBA_USER deploy /work/deploy
# Isolate the released solver's ELF loader/libraries from the Conda geospatial ABI.
COPY --from=solver /usr/local/bin/sfincs /opt/sfincs/bin/sfincs
COPY --from=solver /lib/x86_64-linux-gnu /opt/sfincs/lib
COPY --from=solver /usr/local/lib /opt/sfincs/local-lib
COPY --chown=$MAMBA_USER:$MAMBA_USER deploy/sfincs-native /opt/conda/bin/sfincs
RUN python -m pip install --no-deps -e .
RUN chmod +x /opt/conda/bin/sfincs && mkdir -p /work/data /work/runs /work/configs /work/reports \
    && echo '72b05c4922ef12c686ea6ea17654ccaf7dad292118d71126b22e5432d8c5cacf  /opt/sfincs/bin/sfincs' | sha256sum --check --status
ENV MPLCONFIGDIR=/tmp/matplotlib NUMBA_CACHE_DIR=/tmp/numba XDG_CACHE_HOME=/tmp/cache PYTHONUNBUFFERED=1
# docker compose exec bypasses the Mamba entrypoint; keep CLI tools discoverable.
ENV PATH="/opt/conda/bin:${PATH}"
ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "floodtwin"]
CMD ["doctor"]
