import bpy
from bpy.props import (
    BoolProperty,
    FloatProperty,
    PointerProperty,
    EnumProperty,
    CollectionProperty,
    IntProperty,
)
from bpy.types import PropertyGroup, Panel, Operator, UIList


# --- Global Utility Functions ---
def clamp(x, minimum, maximum):
    return max(minimum, min(x, maximum))


# --- Core Logic ---
def camera_view_bounds_2d(scene, cam_ob, me_ob):
    """
    Returns camera space bounding box of mesh object.
    Returns None if object is invalid, has no vertices, or no projectable points.
    """
    if not me_ob or me_ob.type != "MESH":
        return None

    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh_eval = me_ob.evaluated_get(depsgraph)

    if not mesh_eval:
        return None
    if not hasattr(mesh_eval, "to_mesh") or not hasattr(mesh_eval, "to_mesh_clear"):
        return None

    try:
        me = mesh_eval.to_mesh()
    except RuntimeError:
        me = None

    if not me or not me.vertices:
        if mesh_eval and hasattr(mesh_eval, "to_mesh_clear"):
            mesh_eval.to_mesh_clear()
        return None

    mat = cam_ob.matrix_world.normalized().inverted() @ me_ob.matrix_world
    # Create a copy of the mesh to transform, or transform vertices directly if careful
    temp_mesh = me.copy()
    temp_mesh.transform(mat)

    camera = cam_ob.data
    frame_orig = [-v for v in camera.view_frame(scene=scene)[:3]]
    camera_persp = camera.type != "ORTHO"

    lx = []
    ly = []

    for v in temp_mesh.vertices:  # Use transformed vertices from temp_mesh
        co_local = v.co
        z_cam_dist = -co_local.z

        if camera_persp:
            if z_cam_dist <= 0.0:
                if z_cam_dist == 0.0:
                    lx.append(0.5)
                    ly.append(0.5)
                continue
            if frame_orig[1].z == 0 or frame_orig[2].z == 0 or frame_orig[0].z == 0:
                continue
            min_x_proj = frame_orig[1].x * (z_cam_dist / frame_orig[1].z)
            max_x_proj = frame_orig[2].x * (z_cam_dist / frame_orig[2].z)
            min_y_proj = frame_orig[0].y * (z_cam_dist / frame_orig[0].z)
            max_y_proj = frame_orig[1].y * (z_cam_dist / frame_orig[1].z)
        else:  # Orthographic
            min_x_proj, max_x_proj = frame_orig[1].x, frame_orig[2].x
            min_y_proj, max_y_proj = frame_orig[0].y, frame_orig[1].y

        denom_x = max_x_proj - min_x_proj
        denom_y = max_y_proj - min_y_proj
        x = 0.5 if denom_x == 0.0 else (co_local.x - min_x_proj) / denom_x
        y = 0.5 if denom_y == 0.0 else (co_local.y - min_y_proj) / denom_y
        lx.append(x)
        ly.append(y)

    bpy.data.meshes.remove(temp_mesh)  # Clean up the copied mesh
    mesh_eval.to_mesh_clear()  # Clean up the evaluated mesh data

    if not lx or not ly:
        return None

    min_x_norm = clamp(min(lx), 0.0, 1.0)
    max_x_norm = clamp(max(lx), 0.0, 1.0)
    min_y_norm = clamp(min(ly), 0.0, 1.0)
    max_y_norm = clamp(max(ly), 0.0, 1.0)

    if min_x_norm > max_x_norm:
        min_x_norm, max_x_norm = max_x_norm, min_x_norm
    if min_y_norm > max_y_norm:
        min_y_norm, max_y_norm = max_y_norm, min_y_norm

    return (min_x_norm, max_x_norm, min_y_norm, max_y_norm)


def update_render_border(scene):
    props = scene.dynamic_render_border_props
    cam = scene.camera
    render = scene.render

    if not cam:
        return

    objects_to_process = []
    processed_object_names = set()

    if props.target_source_mode == "OBJECT_LIST":
        for item in props.object_list:
            obj = item.object
            if obj and obj.type == "MESH" and obj.name not in processed_object_names:
                # Check if object is visible in the current view layer and viewport
                if obj.visible_get() and obj.hide_viewport == False:
                    objects_to_process.append(obj)
                    processed_object_names.add(obj.name)
    elif props.target_source_mode == "COLLECTION_LIST":
        for item in props.collection_list:
            coll = item.collection
            if coll:
                for (
                    obj
                ) in coll.all_objects:  # all_objects includes those in sub-collections
                    if obj.type == "MESH" and obj.name not in processed_object_names:
                        if obj.visible_get() and obj.hide_viewport == False:
                            objects_to_process.append(obj)
                            processed_object_names.add(obj.name)

    if not objects_to_process:
        render.use_border = False
        return

    all_object_bounds = []
    for obj in objects_to_process:
        bounds = camera_view_bounds_2d(scene, cam, obj)
        if bounds:
            all_object_bounds.append(bounds)

    if not all_object_bounds:
        render.use_border = False
        return

    overall_min_x = min(b[0] for b in all_object_bounds)
    overall_max_x = max(b[1] for b in all_object_bounds)
    overall_min_y = min(b[2] for b in all_object_bounds)
    overall_max_y = max(b[3] for b in all_object_bounds)

    padding_val = props.padding
    render.border_min_x = clamp(overall_min_x - padding_val, 0.0, 1.0)
    render.border_max_x = clamp(overall_max_x + padding_val, 0.0, 1.0)
    render.border_min_y = clamp(overall_min_y - padding_val, 0.0, 1.0)
    render.border_max_y = clamp(overall_max_y + padding_val, 0.0, 1.0)

    if (
        render.border_min_x >= render.border_max_x
        or render.border_min_y >= render.border_max_y
    ):
        render.use_border = False
    else:
        render.use_border = True


# --- Handler Function ---
def dynamic_border_handler(scene, depsgraph=None):
    if hasattr(scene, "dynamic_render_border_props"):
        props = scene.dynamic_render_border_props
        if props.enable:
            update_render_border(scene)


# --- Property Callbacks ---
def drb_enable_update(self, context):
    if self.enable:
        # The handler is always registered, it checks the enable prop itself.
        update_render_border(context.scene)
    else:
        # The handler is always registered, it checks the enable prop itself.
        # We just need to disable the border when the user unticks 'enable'.
        if context and context.scene:
            render = context.scene.render
            render.use_border = False
            render.border_min_x = 0.0
            render.border_max_x = 1.0
            render.border_min_y = 0.0
            render.border_max_y = 1.0


def drb_settings_update(self, context):
    if hasattr(context.scene, "dynamic_render_border_props"):
        props = context.scene.dynamic_render_border_props
        if props.enable:
            update_render_border(context.scene)


# --- Property Groups for Lists ---
class DRBObjectListItem(PropertyGroup):
    object: PointerProperty(name="Object", type=bpy.types.Object)


class DRBCollectionListItem(PropertyGroup):
    collection: PointerProperty(name="Collection", type=bpy.types.Collection)


# --- Main Properties ---
class DynamicRenderBorderProperties(PropertyGroup):
    enable: BoolProperty(
        name="Enable Dynamic Border", default=False, update=drb_enable_update
    )
    padding: FloatProperty(
        name="Padding",
        default=0.02,
        min=0.0,
        max=0.5,
        subtype="PERCENTAGE",
        precision=2,
        update=drb_settings_update,
    )
    target_source_mode: EnumProperty(
        name="Target Source",
        items=[
            ("OBJECT_LIST", "Object List", "Use a custom list of objects"),
            ("COLLECTION_LIST", "Collection List", "Use a custom list of collections"),
        ],
        default="OBJECT_LIST",
        update=drb_settings_update,
    )
    object_list: CollectionProperty(type=DRBObjectListItem)
    object_list_index: IntProperty(name="Object List Index", default=0)

    collection_list: CollectionProperty(type=DRBCollectionListItem)
    collection_list_index: IntProperty(name="Collection List Index", default=0)
    collection_to_add: PointerProperty(
        name="Collection to Add",
        type=bpy.types.Collection,
        update=drb_settings_update,  # Update if a collection is picked
    )


# --- UI Lists ---
class DRB_UL_ObjectList(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        obj_item = item.object
        if obj_item:
            layout.prop(
                obj_item,
                "name",
                text="",
                emboss=False,
                icon_value=layout.icon(obj_item),
            )
        else:
            layout.label(text="<Empty Slot>", icon="QUESTION")


class DRB_UL_CollectionList(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        coll_item = item.collection
        if coll_item:
            layout.prop(
                coll_item,
                "name",
                text="",
                emboss=False,
                icon_value=layout.icon(coll_item),
            )
        else:
            layout.label(text="<Empty Slot>", icon="QUESTION")


# --- Operators ---
class DRB_OT_ListActionBase(Operator):
    def _update_if_enabled(self, context):
        props = context.scene.dynamic_render_border_props
        if props.enable:
            update_render_border(context.scene)
            context.area.tag_redraw()  # Ensure UI updates if border changes


class DRB_OT_AddObjectToList(DRB_OT_ListActionBase):
    bl_idname = "drb.add_object_to_list"
    bl_label = "Add Selected to Object List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.selected_objects and any(
            obj.type == "MESH" for obj in context.selected_objects
        )

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        current_object_names = {
            item.object.name for item in props.object_list if item.object
        }
        added_count = 0
        for obj in context.selected_objects:
            if obj.type == "MESH" and obj.name not in current_object_names:
                item = props.object_list.add()
                item.object = obj
                current_object_names.add(obj.name)
                added_count += 1
        if added_count > 0:
            props.object_list_index = len(props.object_list) - 1
            self._update_if_enabled(context)
            self.report({"INFO"}, f"Added {added_count} object(s) to list.")
        else:
            self.report(
                {"INFO"}, "No new mesh objects selected to add or already in list."
            )
        return {"FINISHED"}


class DRB_OT_RemoveObjectFromList(DRB_OT_ListActionBase):
    bl_idname = "drb.remove_object_from_list"
    bl_label = "Remove Object from List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = context.scene.dynamic_render_border_props
        return props.object_list and 0 <= props.object_list_index < len(
            props.object_list
        )

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        props.object_list.remove(props.object_list_index)
        props.object_list_index = min(
            max(0, props.object_list_index - 1), len(props.object_list) - 1
        )
        self._update_if_enabled(context)
        self.report({"INFO"}, "Object removed from list.")
        return {"FINISHED"}


class DRB_OT_ClearObjectList(DRB_OT_ListActionBase):
    bl_idname = "drb.clear_object_list"
    bl_label = "Clear Object List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.dynamic_render_border_props.object_list

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        props.object_list.clear()
        props.object_list_index = 0
        self._update_if_enabled(context)
        self.report({"INFO"}, "Object list cleared.")
        return {"FINISHED"}


class DRB_OT_AddCollectionToList(DRB_OT_ListActionBase):
    bl_idname = "drb.add_collection_to_list"
    bl_label = "Add Collection to List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.dynamic_render_border_props.collection_to_add is not None

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        coll_to_add = props.collection_to_add

        current_collection_names = {
            item.collection.name for item in props.collection_list if item.collection
        }
        if coll_to_add.name not in current_collection_names:
            item = props.collection_list.add()
            item.collection = coll_to_add
            props.collection_list_index = len(props.collection_list) - 1
            self._update_if_enabled(context)
            self.report({"INFO"}, f"Collection '{coll_to_add.name}' added to list.")
        else:
            self.report({"INFO"}, f"Collection '{coll_to_add.name}' already in list.")
        return {"FINISHED"}


class DRB_OT_RemoveCollectionFromList(DRB_OT_ListActionBase):
    bl_idname = "drb.remove_collection_from_list"
    bl_label = "Remove Collection from List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        props = context.scene.dynamic_render_border_props
        return props.collection_list and 0 <= props.collection_list_index < len(
            props.collection_list
        )

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        props.collection_list.remove(props.collection_list_index)
        props.collection_list_index = min(
            max(0, props.collection_list_index - 1), len(props.collection_list) - 1
        )
        self._update_if_enabled(context)
        self.report({"INFO"}, "Collection removed from list.")
        return {"FINISHED"}


class DRB_OT_ClearCollectionList(DRB_OT_ListActionBase):
    bl_idname = "drb.clear_collection_list"
    bl_label = "Clear Collection List"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return context.scene.dynamic_render_border_props.collection_list

    def execute(self, context):
        props = context.scene.dynamic_render_border_props
        props.collection_list.clear()
        props.collection_list_index = 0
        self._update_if_enabled(context)
        self.report({"INFO"}, "Collection list cleared.")
        return {"FINISHED"}


class DRB_OT_UpdateDynamicBorderManual(
    Operator
):  # Renamed from DRB_OT_UpdateDynamicBorder
    bl_idname = "render.update_dynamic_border_manual"  # Changed bl_idname
    bl_label = "Update Dynamic Render Border Manually"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.scene
            and hasattr(context.scene, "dynamic_render_border_props")
            and context.scene.dynamic_render_border_props.enable
        )

    def execute(self, context):
        if not context.scene.camera:
            self.report({"WARNING"}, "No active camera in scene.")
            return {"CANCELLED"}
        update_render_border(context.scene)
        if context.scene.render.use_border:
            self.report({"INFO"}, "Render border updated.")
        else:
            self.report(
                {"INFO"},
                "Render border updated (no valid targets or targets off-screen).",
            )
        return {"FINISHED"}


# --- Panel ---
class VIEW3D_PT_DynamicRenderBorder(Panel):
    bl_label = "Dynamic Render Border"
    bl_idname = "VIEW3D_PT_dynamic_render_border"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DynBorder"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        if not hasattr(scene, "dynamic_render_border_props"):
            layout.label(text="Error: Properties not found. Re-enable addon?")
            return

        props = scene.dynamic_render_border_props
        layout.prop(props, "enable")

        col = layout.column()
        col.enabled = props.enable

        col.prop(
            props, "target_source_mode", expand=True
        )  # expand for button-like look

        if props.target_source_mode == "OBJECT_LIST":
            row = col.row()
            row.template_list(
                "DRB_UL_ObjectList",
                "",
                props,
                "object_list",
                props,
                "object_list_index",
                rows=3,
            )

            op_col = row.column(align=True)
            op_col.operator(DRB_OT_AddObjectToList.bl_idname, text="", icon="ADD")
            op_col.operator(
                DRB_OT_RemoveObjectFromList.bl_idname, text="", icon="REMOVE"
            )
            op_col.separator()
            op_col.operator(DRB_OT_ClearObjectList.bl_idname, text="", icon="TRASH")

        elif props.target_source_mode == "COLLECTION_LIST":
            col.prop(props, "collection_to_add", text="")  # Picker for collection
            row = col.row()
            row.template_list(
                "DRB_UL_CollectionList",
                "",
                props,
                "collection_list",
                props,
                "collection_list_index",
                rows=3,
            )

            op_col = row.column(align=True)
            op_col.operator(DRB_OT_AddCollectionToList.bl_idname, text="", icon="ADD")
            op_col.operator(
                DRB_OT_RemoveCollectionFromList.bl_idname, text="", icon="REMOVE"
            )
            op_col.separator()
            op_col.operator(DRB_OT_ClearCollectionList.bl_idname, text="", icon="TRASH")

        col.prop(props, "padding")
        col.operator(
            DRB_OT_UpdateDynamicBorderManual.bl_idname, text="Update Border Now"
        )


# --- Registration ---
classes = (
    DRBObjectListItem,
    DRBCollectionListItem,
    DynamicRenderBorderProperties,
    DRB_UL_ObjectList,
    DRB_UL_CollectionList,
    DRB_OT_AddObjectToList,
    DRB_OT_RemoveObjectFromList,
    DRB_OT_ClearObjectList,
    DRB_OT_AddCollectionToList,
    DRB_OT_RemoveCollectionFromList,
    DRB_OT_ClearCollectionList,
    DRB_OT_UpdateDynamicBorderManual,  # Renamed
    VIEW3D_PT_DynamicRenderBorder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dynamic_render_border_props = PointerProperty(
        type=DynamicRenderBorderProperties
    )

    # Register the handler directly. It will check the 'enable' prop internally.
    if dynamic_border_handler not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(dynamic_border_handler)


def unregister():
    # Unregister the handler.
    if dynamic_border_handler in bpy.app.handlers.frame_change_post:
        try:
            bpy.app.handlers.frame_change_post.remove(dynamic_border_handler)
        except ValueError:
            # Handler was not in the list, which is fine.
            pass

    if hasattr(bpy.types.Scene, "dynamic_render_border_props"):
        del bpy.types.Scene.dynamic_render_border_props
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
