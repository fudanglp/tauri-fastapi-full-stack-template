# DMABUF/Browser Shared Memory for Zero-Copy GPU Rendering

## Overview

DMABUF (Direct Memory Access Buffer) is a Linux kernel mechanism for sharing buffers between devices (GPU, camera, video encoder, etc.) without CPU copies. For Tauri on Linux, this enables zero-copy GPU memory sharing between Rust native rendering and the WebKitGTK webview.

## Why DMABUF?

### Traditional Approach (CPU Copy)
```
Rust GPU → glReadPixels → CPU RAM → IPC → Browser → Upload to GPU
```
- **Slow**: CPU copy bottleneck
- **High latency**: ~10-30ms for 1080p
- **High power**: Memory bandwidth intensive

### DMABUF Approach (Zero-Copy)
```
Rust GPU → DMABUF Handle → Browser → Direct GPU Access
```
- **Fast**: No CPU copies
- **Low latency**: ~1-3ms
- **Efficient**: Minimal power consumption

## Requirements

### System Requirements
- Linux kernel 4.4+ (DMABUF support)
- GPU drivers supporting DMA-BUF export:
  - Intel Mesa (i915)
  - AMD Radeon (amdgpu/radeonsi)
  - NVIDIA (proprietary driver 515+ with GBM backend)
- Compositor supporting DMA-BUF (Wayland: Weston, KWin, Mutter; X11: limited)

### Browser/WebKitGTK Requirements
- WebKitGTK 2.40+ with DMA-BUF import support
- EGL 1.5+ with `EGL_EXT_image_dma_buf_import` extension
- Check support:
  ```bash
  # Check EGL extensions
 eglinfo | grep dma_buf

  # Check WebKitGTK version
  pkg-config --modversion webkit2gtk-4.1
  ```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Tauri App                           │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐         ┌─────────────────────────┐   │
│  │  Rust Backend   │         │    WebKitGTK Frontend   │   │
│  │                 │         │                         │   │
│  │  ┌───────────┐  │         │  ┌───────────────────┐  │   │
│  │  │  OpenGL   │  │         │  │      <canvas>     │  │   │
│  │  │  Render   │  │         │  │   WebGL Context   │  │   │
│  │  └─────┬─────┘  │         │  └─────────┬─────────┘  │   │
│  │        │        │         │            │             │   │
│  │  ┌─────▼─────┐  │ DMABUF  │  ┌─────────▼─────────┐  │   │
│  │  │ EGL/G BM │──┼─────────┼─▶│  WebGL Texture    │  │   │
│  │  │  Export  │  │ FD      │  │   Import          │  │   │
│  │  └──────────┘  │         │  └───────────────────┘  │   │
│  └─────────────────┘         └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
         │                                        │
         ▼                                        ▼
    GPU Memory (Shared)                    GPU Memory
```

## Implementation Options

### Option 1: WebGL VideoTexture (MediaSource)

Use WebCodecs API with VideoFrame containing DMABUF:

```rust
// Rust - Export DMABUF
use drm::buffer::DrmBuffer;
use egl::EGLDisplay;

let dmabuf_fd = export_gl_buffer_to_dmabuf(gl_texture);
// Send fd via IPC (SCM_RIGHTS)
```

```javascript
// Frontend - Import as VideoFrame
const videoFrame = new VideoFrame(dmabuf_handle, {
    timestamp: 0,
    codedWidth: 1920,
    codedHeight: 1080
});
// Render to canvas
ctx.drawImage(videoFrame, 0, 0);
```

**Pros:**
- Standard web API
- Hardware video decoder integration

**Cons:**
- Browser support varies (Chrome/Chromium better)
- Limited to video-like formats

### Option 2: WebGL Texture with EGL Extension (Advanced)

Direct EGL texture sharing:

```rust
// Rust backend
use egl::{EGLDisplay, EGLImage};
use gbm::{BufferObject, Format};

// Create GBM buffer
let gbm_device = gbm::Device::open("/dev/dri/renderD128").unwrap();
let gbm_bo = gbm_device.create_buffer::<Format>(
    1920, 1080,
    gbm::Format::Argb8888,
    gbm::BufferObjectFlags::RENDERING
).unwrap();

// Export to DMABUF
let dmabuf_fd = gbm_bo.export_fd().unwrap();

// Create EGLImage from DMABUF
let egl_image = egl.create_image(
    egl::NO_CONTEXT,
    EGL_LINUX_DMA_BUF_EXT,
    None,
    &EGLImageAttribs {
        width: 1920,
        height: 1080,
        format: fourcc('AR24'),
        planes: &[EGLPlaneAttrib {
            fd: dmabuf_fd,
            offset: 0,
            pitch: stride,
        }]
    }
)?;

// Render to texture
gl::framebuffer_texture_2d(
    gl::READ_FRAMEBUFFER,
    gl::COLOR_ATTACHMENT0,
    gl::TEXTURE_2D,
    egl_image.gl_texture_id,
    0
);
```

```javascript
// Frontend - Not directly supported in standard WebGL!
// Requires browser extensions or custom WebKitGTK build
```

**Current Limitation:**
WebKitGTK doesn't expose DMABUF texture import to WebGL content directly. This is a research/experimental area.

### Option 3: PipeWire + Portal (Recommended for Linux)

Use PipeWire for screen sharing/streaming:

```rust
// Use xdg-desktop-portal
use ashpd::desktop::screencast::Screencast;

let screencast = Screencast::new().await?;
let session = screencast.create_session().await?;
// PipeWire handles DMABUF automatically
```

**Pros:**
- Standard Linux desktop integration
- DMABUF handled by PipeWire
- Works with Wayland and X11

**Cons:**
- Requires PipeWire running
- More setup complexity
- Overkill for single-app use case

## Current Status

### WebKitGTK DMABUF Support

WebKitGTK can import DMABUF internally for:
- Video playback (GStreamer with DMABUF)
- Camera capture (v4l2 with DMABUF)

**However**, DMABUF import to **WebGL contexts is not currently exposed** to JavaScript content.

Check for updates:
- [WebKit Bug Tracker](https://bugs.webkit.org/)
- Search for: "DMA-BUF WebGL texture import"

### Alternative: Video Element + GStreamer

WebKitGTK supports GStreamer with DMABUF for video elements:

```rust
// Use GStreamer to push DMABUF frames
use gstreamer as gst;
use gstreamer_app as gst_app;

let pipeline = gst::parse::launch(
    "appsrc name=src ! video/x-raw,format=ARGB,width=1920,height=1080 ! \
     glupload ! glcolorconvert ! gldownload ! \
     videoconvert ! appsink name=sink"
)?;
```

```javascript
// Display in <video> element (not <canvas>)
const video = document.querySelector('#output-video');
video.srcObject = gstStream;
```

## Recommended Approach (2025)

Given current WebKitGTK limitations, the **practical options** are:

### 1. For Most Use Cases: WebGL in Frontend
Use Three.js with `BufferGeometry` for point clouds - direct GPU access, no copies needed.

### 2. For Heavy Rust Processing: Canvas Image Streaming
Accept the CPU copy for compatibility:
```rust
// Read pixels
let mut pixels = vec![0u8; (width * height * 4) as usize];
gl::read_pixels(0, 0, width, height, gl::RGBA, gl::UNSIGNED_BYTE, pixels.as_mut_ptr());
// Send via IPC
tauri::event::emit("render-frame", &pixels)?;
```

### 3. Wait for WebGPU + DMABUF
WebGPU is adding better external texture support. Track:
- [WebGPU ExternalTexture](https://gpuweb.github.io/gpuweb/#external-texture)
- WebKitGTK WebGPU implementation progress

## Example: Check System DMABUF Support

```bash
# Check kernel version
uname -r  # Should be 4.4+

# Check GPU DRM support
ls -l /dev/dri/
# Should show renderD128 or similar

# Check EGL extensions
eglinfo | grep -i dma_buf
# Should show: EGL_EXT_image_dma_buf_import

# Check GBM support
pkg-config --exists gbm && echo "GBM available"

# Check PipeWire
pactl info | grep PipeWire
```

## Dependencies (Cargo.toml)

```toml
[dependencies]
# GBM for buffer allocation
gbm = "0.15"

# EGL for image creation
egl = { version = "0.3", features = ["dynamic"] }

# DRM for buffer handling
drm = "0.13"

# Optional: PipeWire
pipewire = "0.8"
ashpd = "0.9"  # xdg-desktop-portal
```

## Performance Expectations

| Method | 1080p @ 60fps | Latency | Compatibility |
|--------|---------------|---------|---------------|
| Direct WebGL (frontend) | 0.5ms | 1-2ms | ⭐⭐⭐⭐⭐ |
| DMABUF + Video element | 1-2ms | 2-5ms | ⭐⭐⭐ |
| Canvas streaming (CPU) | 8-15ms | 15-30ms | ⭐⭐⭐⭐⭐ |
| Raw DMABUF to WebGL | N/A | N/A | ⭐ (experimental) |

## References

### Documentation
- [Linux DMA-BUF Guide](https://www.kernel.org/doc/html/latest/driver-api/dma-buf.html)
- [Mesa/EGL DMA-BUF Extensions](https://docs.mesa3d.org/specs/EGL_EXT_image_dma_buf_import.txt)
- [GBM API Reference](https://gitlab.freedesktop.org/mesa/mesa/-/blob/master/src/gbm/main/gbm.h)
- [WebGPU External Texture](https://gpuweb.github.io/gpuweb/#external-texture)

### Libraries
- [gbm-rs](https://crates.io/crates/gbm) - GBM bindings
- [egl-rs](https://crates.io/crates/egl) - EGL bindings
- [drm-rs](https://crates.io/crates/drm) - DRM bindings
- [ashpd](https://crates.io/crates/ashpd) - xdg-desktop-portal

### Projects Using DMABUF
- [Firefox VA-API DMABUF](https://bugzilla.mozilla.org/show_bug.cgi?id=1472429)
- [GStreamer DMA-BUF](https://gstreamer.freedesktop.org/documentation/nvcodec/overview.html)
- [PipeWire Screen Sharing](https://docs.pipewire.org/page_man_pipewire-screen-share_1html/)

### Tracking Issues
- [WebKit: WebGL DMABUF import](https://bugs.webkit.org/show_bug.cgi?id=12345) *(search for relevant tickets)*
- [Chromium: Ozone Native DMABUF](https://chromium.googlesource.com/chromium/src/+/HEAD/docs/ozone_dmabuf.md)

## Conclusion

DMABUF sharing is **technically possible** on Linux with WebKitGTK, but **not directly exposed** to WebGL content in a practical way yet. For most Tauri applications:

1. **Use frontend WebGL** (Three.js, deck.gl) for interactive 3D
2. **Use canvas streaming** for Rust-generated frames when needed
3. **Monitor WebGPU** development for future external texture support

If you're building a research/experimental project and want to explore DMABUF deeply, consider building a custom WebKitGTK build or contributing to WebKit's DMABUF WebGL import feature.
