import os
import subprocess
import struct

TEXCONV_PATH = "texconv"  # Change to absolute path if texconv.exe isn't in your PATH or script folder

def get_dds_status(file_path):
    """
    Checks if a DDS is uncompressed/legacy or already in a safe SSE format.
    """
    # DDS layout: "DDS " (4) + DDS_HEADER (124). DDS_PIXELFORMAT starts at 76:
    # dwFlags @ 80, dwFourCC @ 84. Optional DDS_HEADER_DXT10 starts at 128 (dxgiFormat first).
    DDPF_ALPHAPIXELS = 0x1
    DDPF_ALPHA = 0x2
    DDPF_FOURCC = 0x4
    DDPF_RGB = 0x40
    DDPF_LUMINANCE = 0x20000
    # BC1, BC2, BC3, BC4, BC5, BC7 (UNORM / SRGB / SNORM variants)
    SAFE_DXGI_FORMATS = {71, 72, 74, 75, 77, 78, 80, 81, 83, 84, 98, 99}
    SAFE_FOURCCS = {b"DXT1", b"DXT2", b"DXT3", b"DXT4", b"DXT5",
                    b"ATI1", b"BC4U", b"BC4S", b"ATI2", b"BC5U", b"BC5S"}
    try:
        with open(file_path, "rb") as f:
            header = f.read(148)
        if len(header) < 128 or header[:4] != b"DDS ":
            return "invalid"

        pf_flags = struct.unpack_from("<I", header, 80)[0]
        four_cc = header[84:88]

        if pf_flags & DDPF_FOURCC:
            if four_cc == b"DX10":
                if len(header) < 132:
                    return "invalid"
                dxgi_format = struct.unpack_from("<I", header, 128)[0]
                return "ok" if dxgi_format in SAFE_DXGI_FORMATS else "unknown"
            return "ok" if four_cc in SAFE_FOURCCS else "unknown"

        if pf_flags & (DDPF_RGB | DDPF_ALPHA | DDPF_ALPHAPIXELS | DDPF_LUMINANCE):
            return "uncompressed"

        return "unknown"
    except Exception:
        return "error"

def batch_convert_textures(target_directory):
    print(f"Scanning and converting uncompressed textures in: {target_directory}\n")
    converted_count = 0
    
    for root, dirs, files in os.walk(target_directory):
        for file in files:
            if file.lower().endswith(".dds"):
                full_path = os.path.join(root, file)
                status = get_dds_status(full_path)
                
                if status == "uncompressed":
                    print(f"[CONVERTING] {file} (Status: {status})")
                    
                    # Determine format: Normal maps (_n.dds) need BC5, others need BC7
                    if "_n.dds" in file.lower():
                        # BC5 for normal maps
                        cmd = [
                            TEXCONV_PATH,
                            "-f", "BC5_UNORM",
                            "-y", # Overwrite output
                            "-o", root,
                            full_path
                        ]
                    else:
                        # BC7 for diffuse/hair/eyes/misc
                        cmd = [
                            TEXCONV_PATH,
                            "-f", "BC7_UNORM",
                            "-srgb",
                            "-y",
                            "-o", root,
                            full_path
                        ]
                    
                    try:
                        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                        converted_count += 1
                    except subprocess.CalledProcessError as e:
                        print(f"  [ERROR] Failed to convert {file}: {e.stderr.decode('utf-8', errors='ignore')}")
                    except FileNotFoundError:
                        print(f"  [CRITICAL ERROR] 'texconv' executable not found. Ensure texconv.exe is in PATH or script directory.")
                        return
                elif status == "ok":
                    print(f"[SKIPPED] {file} (Already compliant)")
                else:
                    print(f"[SKIPPED] {file} (Status: {status} - review manually)")

    print(f"\n--- Conversion Complete ---")
    print(f"Successfully converted {converted_count} files to SSE-compliant formats.")

if __name__ == "__main__":
    mod_textures_path = r"F:\_VORTEX_MODS\skyrimse\SexLabAlicia\textures\azmoscreens\statues"
    if os.path.exists(mod_textures_path):
        batch_convert_textures(mod_textures_path)
    else:
        print(f"Path '{mod_textures_path}' not found. Place script inside your mod folder or update path.")
 