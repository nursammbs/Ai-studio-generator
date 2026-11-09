# Real-video smoke-test source

The CI test downloads the following NASA Scientific Visualization Studio source into a temporary directory, runs the clipper pipeline, then removes the input and rendered output when the test exits:

- **Video:** Sarah Jones, Research Scientist, NASA's Goddard Space Flight Center — [GOLD Resources (NASA SVS, ID 12825)](https://svs.gsfc.nasa.gov/12825/)
- **Direct test download:** `https://svs.gsfc.nasa.gov/vis/a010000/a012800/a012825/Sarah_Jones.webm`
- **Reference captions:** `https://svs.gsfc.nasa.gov/vis/a010000/a012800/a012825/SarahJones.en_US.srt`
- **Credit:** NASA's Goddard Space Flight Center; scientist Sarah L. Jones (NASA/GSFC).

The captions are used only to check word error rate. The video and generated clips are not committed, published, uploaded as workflow artifacts, or used as product marketing material. NASA's [media usage guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) note that media with an identifiable person can require permission for commercial use; this CI-only fixture is downloaded ephemerally and its output is discarded.

