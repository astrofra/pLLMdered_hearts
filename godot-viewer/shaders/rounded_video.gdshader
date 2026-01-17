shader_type canvas_item;
render_mode unshaded;

uniform float radius = 24.0;

void fragment() {
    vec4 color = texture(TEXTURE, UV);
    vec2 tex_size = vec2(1.0) / TEXTURE_PIXEL_SIZE;
    float r = radius;
    vec2 pixel = UV * tex_size;
    vec2 min_dist = min(pixel, tex_size - pixel);

    if (min_dist.x < r && min_dist.y < r) {
        vec2 corner = vec2(
            pixel.x < r ? r : tex_size.x - r,
            pixel.y < r ? r : tex_size.y - r
        );
        float dist = distance(pixel, corner);
        if (dist > r) {
            color.a = 0.0;
        }
    }

    COLOR = color;
}
