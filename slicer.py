from dataclasses import dataclass
from pathlib import Path
from subprocess import call
from PIL import Image, ImageDraw
import os
import struct
import time


BASE_DIR = Path(__file__).resolve().parent
INPUT_STL = BASE_DIR / "test1.stl"
OUTPUT_DIR = BASE_DIR / "generated-files"
OPENSCAD_BIN = Path(r"C:\Program Files\OpenSCAD\openscad.com")

MAX_LAYERS = 999
LAYER_STEP = 0.6
STOP_HEIGHT = 0.8


@dataclass
class SliceState:
    finalists: list
    move_x: float
    move_y: float
    move_z: float
    height: float


def is_binary_stl(stl_path: Path) -> bool:
    """Detect binary STL by validating expected byte size from triangle count."""
    file_size = stl_path.stat().st_size
    if file_size < 84:
        return False

    with stl_path.open("rb") as file_obj:
        header = file_obj.read(84)

    triangle_count = struct.unpack("<I", header[80:84])[0]
    expected_size = 84 + triangle_count * 50
    return expected_size == file_size


def read_bottom_faces(stl_path: Path) -> tuple[list, float, float]:
    """Read an ASCII STL and return faces that lie on its lowest Z plane."""
    if is_binary_stl(stl_path):
        raise ValueError(
            f"Binary STL is not supported by this parser: {stl_path}. "
            "Export ASCII STL or add binary STL parsing."
        )

    loops = []
    in_loop = False
    current_loop = []

    with stl_path.open("r", encoding="utf-8", errors="ignore") as file_obj:
        for line in file_obj:
            normalized = line.replace(" ", "").strip().lower()
            if normalized == "outerloop":
                in_loop = True
                current_loop = []
                continue
            if normalized == "endloop":
                in_loop = False
                loops.append(current_loop)
                continue
            if in_loop:
                current_loop.append(line.strip())

    parsed_loops = []
    for loop in loops:
        parsed_loop = []
        for vertex_line in loop:
            parts = vertex_line.split()
            if len(parts) >= 4 and parts[0].lower() == "vertex":
                parsed_loop.append(parts)
        if len(parsed_loop) == 3:
            parsed_loops.append(parsed_loop)

    coplanar_triangles = []
    z_values = []
    for triangle in parsed_loops:
        z0 = triangle[0][3]
        if z0 == triangle[1][3] and z0 == triangle[2][3]:
            coplanar_triangles.append(triangle)
            z_values.append(float(z0))

    if not z_values:
        raise ValueError(f"Could not find coplanar bottom triangles in {stl_path}")

    min_z = min(z_values)
    max_z = max(z_values)

    bottom_triangles = []
    for triangle in coplanar_triangles:
        if float(triangle[0][3]) == min_z:
            cleaned_triangle = []
            for vertex in triangle:
                cleaned_triangle.append([vertex[1], vertex[2], vertex[3]])
            bottom_triangles.append(cleaned_triangle)

    return bottom_triangles, min_z, max_z


def find_center_offset(finalists: list) -> tuple[float, float]:
    """Compute XY translation needed to center geometry in a 100x100 bed."""
    xs = []
    ys = []
    for triangle in finalists:
        for vertex in triangle:
            xs.append(float(vertex[0]))
            ys.append(float(vertex[1]))

    highest_x = max(xs)
    lowest_x = min(xs)
    highest_y = max(ys)
    lowest_y = min(ys)

    move_x = 50 - (highest_x - (highest_x - lowest_x) / 2)
    move_y = 50 - (highest_y - (highest_y - lowest_y) / 2)
    return move_x, move_y


def create_image(image_base_path: Path, finalists: list) -> None:
    """Render bottom triangles to PNG for visual debugging."""
    img = Image.new(mode="RGB", size=(1000, 1000), color="white")
    draw = ImageDraw.Draw(img)

    for triangle in finalists:
        points = []
        for vertex in triangle:
            points.append((float(vertex[0]) * 10, float(vertex[1]) * 10))
        draw.polygon(points, fill="black")

    img.save(str(image_base_path) + ".png")


def create_layer(
    input_stl_path: Path,
    scad_path: Path,
    distance: float,
    move_x: float,
    move_y: float,
    move_z: float,
) -> None:
    """Write a SCAD file that slices a horizontal layer from the source STL."""
    path_for_scad = str(input_stl_path).replace("\\", "/")
    text = """difference(){{
            difference(){{
                translate([{},{},{}]){{
                import("{}");
                }}
                cube([100,100,{}]);
                    }}
                translate([0,0,{}]){{
                cube([100,100,100]);
                    }}
            }}""".format(move_x, move_y, move_z, path_for_scad, distance, distance + 0.8)
    with scad_path.open("w", encoding="utf-8") as file_obj:
        file_obj.write(text)


def to_stl(scad_path: Path, stl_output_path: Path) -> None:
    """Run OpenSCAD to convert SCAD into STL."""
    cmd = [str(OPENSCAD_BIN), "-o", str(stl_output_path), str(scad_path)]
    result = call(cmd)
    if result != 0:
        raise RuntimeError(f"OpenSCAD failed with exit code {result}: {scad_path}")


def cleanup_intermediate_files(output_dir: Path, total_layers: int) -> None:
    """Delete generated SCAD and STL files, keep PNG previews."""
    for i in range(1, total_layers + 1):
        (output_dir / f"wilson_{i}.stl").unlink(missing_ok=True)
        (output_dir / f"wilson_{i}.scad").unlink(missing_ok=True)


def main() -> None:
    start = time.time()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    finalists, min_z, max_z = read_bottom_faces(INPUT_STL)
    move_x, move_y = find_center_offset(finalists)
    move_z = -min_z
    remaining_height = max_z - min_z

    created_layers = 0

    for i in range(1, MAX_LAYERS + 1):
        if remaining_height < STOP_HEIGHT:
            break

        distance = i * LAYER_STEP
        base_name = OUTPUT_DIR / f"wilson_{i}"
        scad_path = base_name.with_suffix(".scad")
        stl_path = base_name.with_suffix(".stl")

        create_layer(INPUT_STL, scad_path, distance, move_x, move_y, move_z)
        to_stl(scad_path, stl_path)

        if not stl_path.exists():
            raise FileNotFoundError(f"Expected generated STL was not created: {stl_path}")

        finalists, _, _ = read_bottom_faces(stl_path)
        create_image(base_name, finalists)

        remaining_height -= LAYER_STEP
        created_layers += 1

    cleanup_intermediate_files(OUTPUT_DIR, created_layers)
    print(time.time() - start)


if __name__ == "__main__":
    main()