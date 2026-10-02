// primitrace: svgo's preset-default with native primitives kept. Converting circles,
// ellipses and rects to paths would hide the primitives the vectoriser fits, and the complexity
// metrics (nodes, primitive share) are counted on this serialiser's output.
export default {
  multipass: true,
  floatPrecision: 2,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          convertShapeToPath: false,
          // Colours stay #rrggbb so the palette reads back exactly (no "red", no "#f00").
          convertColors: { shortname: false, shorthex: false },
        },
      },
    },
  ],
};
