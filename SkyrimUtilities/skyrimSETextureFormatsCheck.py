import os
import struct

def get_dds_compression(file_path):
    try:
        with open(file_path, "rb") as f:
            magic = f.read(4)
            if magic != b"DDS ":
                return "Not a valid DDS file"
            
            # Read header
            header = f.read(124)
            
            # Check for DX10 extended header
            f.seek(128)
            magic_10 = f.read(4)
            if magic_10 == b"DX10":
                dxgi_format = struct.unpack("<I", f.read(4))[0]
                dxgi_map = {
                    71: "BC1 (DXT1)",
                    74: "BC3 (DXT5)",
                    80: "BC5U / BC5_UNORM",
                    98: "BC7_UNORM",
                    99: "BC7_UNORM_SRGB"
                }
                return dxgi_map.get(dxgi_format, f"DX10 Format Code: {dxgi_format}")
            
            # Read Pixel Format flags (offset 84 in file, which is header[80:84])
            f.seek(84)
            pf_flags = struct.unpack("<I", f.read(4))[0]
            f.seek(88)
            four_cc = f.read(4)
            
            # Check FourCC if present
            if pf_flags & 0x00000004: # DDPF_FOURCC
                four_cc_str = four_cc.decode("ascii", errors="ignore").strip('\x00')
                if four_cc_str:
                    if four_cc_str == "DXT1":
                        return "DXT1 / BC1"
                    elif four_cc_str == "DXT3":
                        return "DXT3 / BC2"
                    elif four_cc_str == "DXT5":
                        return "DXT5 / BC3"
                    elif four_cc_str in ["ATI2", "BC5U"]:
                        return "BC5 (Normal Map)"
                    else:
                        return f"FourCC: {four_cc_str}"
            
            # If no FourCC, check if it's uncompressed RGB/RGBA (DDPF_RGB = 0x00000040)
            f.seek(80) # Pixel format dwSize is at 76, dwFlags at 80
            pf_flags_full = struct.unpack("<I", f.read(4))[0]
            f.seek(84)
            pf_flags = struct.unpack("<I", f.read(4))[0]
            f.seek(92)
            rgb_bit_count = struct.unpack("<I", f.read(4))[0]
            
            if pf_flags & 0x00000040: # DDPF_RGB
                return f"UNCOMPRESSED RGB ({rgb_bit_count}-bit) [HIGH CTD RISK IN SSE]"
            elif pf_flags & 0x00000002: # DDPF_ALPHAPIXELS
                return f"UNCOMPRESSED RGBA ({rgb_bit_count}-bit) [HIGH CTD RISK IN SSE]"
            
            return f"Unknown Legacy Format (Flags: {hex(pf_flags)})"
            
    except Exception as e:
        return f"Error reading file: {e}"

def audit_mod_textures(target_directory):
    print(f"Scanning directory for textures: {target_directory}\n")
    unsupported_count = 0
    total_files = 0
    
    for root, dirs, files in os.walk(target_directory):
        for file in files:
            if file.lower().endswith(".dds"):
                total_files += 1
                full_path = os.path.join(root, file)
                format_type = get_dds_compression(full_path)
                
                if "UNCOMPRESSED" in format_type or "Unknown" in format_type or "Error" in format_type:
                    unsupported_count += 1
                    print(f"[CRASH RISK] {file} -> Format: {format_type}")
                else:
                    print(f"[OK] {file} -> {format_type}")

    print("\n--- Audit Complete ---")
    print(f"Total .dds files scanned: {total_files}")
    print(f"Flagged high-risk files: {unsupported_count}")
 

if __name__ == "__main__":
    # Replace with your specific mod's texture path or let it run in the current folder
    mod_textures_path = r"F:\_VORTEX_MODS\skyrimse\SexLabAlicia\textures\azmoscreens\statues" 
    if os.path.exists(mod_textures_path):
        audit_mod_textures(mod_textures_path)
    else:
        print(f"Path '{mod_textures_path}' not found. Place script inside your mod folder or update path.")