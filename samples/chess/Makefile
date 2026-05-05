build: sandbox.wasm ui.bundle.js

sandbox.bundle.js: sandbox.js node_modules
	npx esbuild sandbox.js --bundle --format=esm --platform=neutral '--external:pxc:sandbox/*' --main-fields=module,main --outfile=sandbox.bundle.js

sandbox.wasm: sandbox.bundle.js pxc.wit
	npx componentize-js sandbox.bundle.js --wit pxc.wit --world-name activity --disable http --disable fetch-event -o sandbox.wasm

ui.bundle.js: ui.js node_modules
	npx esbuild ui.js --bundle --format=esm --outfile=ui.bundle.js

node_modules: package.json
	npm install
