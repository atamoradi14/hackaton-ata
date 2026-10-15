import {build} from 'esbuild';
await build({entryPoints:['scene.js'],bundle:true,format:'esm',minify:true,outfile:'scene.bundle.js'});
await build({entryPoints:['hybrid.js'],bundle:true,format:'esm',minify:true,outfile:'hybrid.bundle.js',define:{CESIUM_BASE_URL:JSON.stringify('/vendor/cesium/')}});
