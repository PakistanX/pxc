// Student-side init for the PXC xblock. Open edX wires this up via
// frag.initialize_js("PxcStudentXBlock") and invokes it once the fragment is
// in the DOM with the XBlock runtime + the root element.
//
// Sole responsibility: register the <pxc-activity> custom element. The class
// itself (XBlockPXC, defined in xblock_pxc.js + its pxc.js base) is loaded
// via add_javascript_url earlier in the same fragment.
function PxcStudentXBlock(runtime, element) {
  if (!customElements.get("pxc-activity")) {
    customElements.define("pxc-activity", XBlockPXC);
  }
}
