import {build} from 'esbuild';
await build({entryPoints:['scene.js'],bundle:true,format:'esm',minify:true,outfile:'scene.bundle.js'});
await build({entryPoints:['terrain-workspace.js'],bundle:true,format:'esm',minify:true,outfile:'terrain3d.bundle.js'});
await build({entryPoints:['hybrid.js'],bundle:true,format:'esm',minify:true,outfile:'hybrid.bundle.js',define:{CESIUM_BASE_URL:JSON.stringify('/vendor/cesium/')}});
