# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110 - 1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
        "name": "MatLib",
        "description":"Materials Librarian",
        "author":"Shams Kitz",
        "version":(3,1),
        "blender":(2,80,0),
        "location":"Properties",
        "warning":"",
        "wiki_url":"",
        "tracker_url":"https://github.com/dustractor/matlib.git",
        "category": "Material"
        }

import sqlite3
import pathlib
import bpy


def _(c=None,r=[]):
    if c:
        r.append(c)
        return c
    return r


class MaterialsLibrarian(sqlite3.Connection):
    def __init__(self,name,**kwargs):
        super().__init__(name,**kwargs)
        self.cu = self.cursor()
        self.cu.row_factory = lambda c,r:r[0]
        self.executescript(
        """
        pragma foreign_keys=ON;
        pragma recursive_triggers=ON;

        create table if not exists paths (
        id integer primary key,
        name text,
        mtime real,
        unique (name) on conflict replace);

        create table if not exists blends (
        id integer primary key,
        path_id integer,
        name text,
        mtime real,
        unique (name) on conflict replace,
        foreign key (path_id) references paths(id) on delete cascade);

        create table if not exists materials (
        id integer primary key,
        blend_id integer,
        name text,
        unique (name) on conflict replace,
        foreign key (blend_id) references blends(id) on delete cascade);

        create table if not exists active_path (
        state integer default 0,
        path_id integer,
        unique (state) on conflict replace,
        foreign key (path_id) references paths(id) on delete cascade);

        create view if not exists materials_view as
        select id,name from materials where blend_id in (select id from blends
        where path_id=(select path_id from active_path where state=0));

        """)
        self.commit()
    def path(self,path_id):
        return self.cu.execute(
                "select name from paths where id=?",
                (path_id,)).fetchone()
    @property
    def paths(self):
        yield from self.execute("select id,name from paths")
    def add_path(self,path):
        self.active_path = self.execute(
                "insert into paths (name) values (?)", (path,)).lastrowid
    @property
    def active_path(self):
        return self.cu.execute(
                "select path_id from active_path where state=0").fetchone()
    @active_path.setter
    def active_path(self,path_id):
        self.execute("insert into active_path (path_id) values (?)",
                (path_id,))
        self.prune_gone_blends(path_id)
        self.add_blends_in_path(path_id)
        self.commit()
    @property
    def materials(self):
        yield from self.execute("select id,name from materials_view")
    def material_names(self):
        return self.cu.execute("select name from materials_view").fetchall()
    def add_blends_in_path(self,path_id):
        path = self.cu.execute(
                "select name from paths where id=?",
                (path_id,)).fetchone()
        for bpath in pathlib.Path(path).glob("**/*.blend"):
            blend = str(bpath)
            cur_bmtime = bpath.stat().st_mtime
            already_in = self.cu.execute(
                    "select count(*) from blends where name=?",
                    (blend,)).fetchone()
            if already_in:
                lib_bmtime = self.cu.execute(
                        "select mtime from blends where name=?",
                        (blend,)).fetchone()
                if lib_bmtime == cur_bmtime:
                    print(f"skipping {blend}: modification time was the same.")
                    continue
            blend_id = self.execute(
                    "insert into blends (path_id,name,mtime) values (?,?,?)",
                    (path_id,blend,cur_bmtime)).lastrowid
            with bpy.data.libraries.load(blend) as (data_from,data_to):
                blend_matcount = len(data_from.materials)
                for matname in data_from.materials:
                    self.execute(
                        "insert into materials (blend_id,name) values (?,?)",
                        (blend_id,matname))
            word = ["materials","material"][blend_matcount==1]
            print(f"added {blend} with {blend_matcount} {word}.")
    def prune_gone_blends(self,path_id):
        for i,b in self.execute("select id,name from blends where path_id=?",
                (path_id,)):
            if not pathlib.Path(b).exists():
                print(f"Removed trace of {b}")
                self.execute("delete from blends where id=?",(i,))


class MaterialsLibrary:
    _handle = None
    @property
    def cx(self):
        if not self._handle:
            self._handle = sqlite3.connect(
                    bpy.utils.user_resource(
                        "CONFIG",
                        path="matlib.db"),
                    factory=MaterialsLibrarian)
        return self._handle


db = MaterialsLibrary()


@_
class MATLIB_OT_send_material(bpy.types.Operator):
    bl_idname = "matlib.send_material"
    bl_label = "Send to Library"
    bl_description = "Send current material to the library"
    bl_options = {"INTERNAL"}
    force_overwrite: bpy.props.BoolProperty(
            default=False,
            name="Overwrite existing Material?",
            description="Check this box and choose OK to overwrite the "
                        "previously existing material of same name.")
    matfile: bpy.props.StringProperty(default="",
            name="or rename it",
            description="Edit to change the name of the file in which "
                        "the material will be kept.")
    def draw(self,context):
        self.layout.box().prop(self,"force_overwrite")
        self.layout.box().prop(self,"matfile")
    @classmethod
    def poll(self,context):
        return all((context.material,db.cx.active_path))
    def invoke(self,context,event):
        path_id = db.cx.active_path
        path = db.cx.cu.execute("select name from paths where id=?",
                (path_id,)
                ).fetchone()
        matfile_path = pathlib.Path(path)/f"{context.material.name}.blend"
        self.matfile = str(matfile_path)
        if matfile_path.exists():
            context.window_manager.invoke_props_dialog(self,width=720)
            return {"RUNNING_MODAL"}
        else:
            return self.execute(context)
    def execute(self,context):
        matfile_path = pathlib.Path(self.matfile)
        if not matfile_path.exists() or self.force_overwrite:
            bpy.data.libraries.write(
                    str(matfile_path),
                    set([context.material]),
                    fake_user=True)
        db.cx.active_path = db.cx.active_path
        return {"FINISHED"}


@_
class MATLIB_OT_load_material(bpy.types.Operator):
    bl_idname = "matlib.load_material"
    bl_label = "Load Material"
    bl_options = {"INTERNAL"}
    mat_id: bpy.props.IntProperty()
    def execute(self,context):
        print("loading material",self.mat_id)
        blend,matname = db.cx.execute(
                """select blends.name,materials.name from materials
                join blends on blends.id=materials.blend_id
                where materials.id=? """,
                (self.mat_id,)).fetchone()
        with bpy.data.libraries.load(blend) as (data_from,data_to):
            data_to.materials = [matname]
        mat = data_to.materials[0]
        mat.use_fake_user = False
        if hasattr(context,"material_slot"):
            if not context.material_slot:
                bpy.ops.object.material_slot_add()
            context.material_slot.material = mat
        elif hasattr(context.view_layer.objects.active,"material_slots"):
            if not context.view_layer.objects.active.material_slots:
                bpy.ops.object.material_slot_add()
            ob = context.view_layer.objects.active
            ob.material_slots[ob.active_material_index].material = mat
        return {"FINISHED"}


@_
class MATLIB_OT_select_path(bpy.types.Operator):
    bl_idname = "matlib.select_path"
    bl_label = "Select Path"
    bl_options = {"INTERNAL"}
    bl_description = "hold shift to open in file browser"
    path_id: bpy.props.IntProperty()
    def invoke(self,context,event):
        if event.shift:
            path = db.cx.path(self.path_id)
            if path:
                bpy.ops.wm.path_open(filepath=path)
                return {"FINISHED"}
            else:
                return {"CANCELLED"}
        elif event.alt:
            db.cx.execute("delete from paths where id=?",(self.path_id,))
            db.cx.commit()
            return {"FINISHED"}
        return self.execute(context)
    def execute(self,context):
        print("selecting path",self.path_id)
        db.cx.active_path = self.path_id
        return {"FINISHED"}


@_
class MATLIB_OT_add_path(bpy.types.Operator):
    bl_idname = "matlib.add_path"
    bl_label = "Add Library Path..."
    bl_options = {"INTERNAL"}
    directory: bpy.props.StringProperty(
            subtype="DIR_PATH",
            maxlen=1024,
            default="")
    def invoke(self,context,event):
        if not self.directory or (
                self.directory and not pathlib.Path(self.directory).is_dir()
                ):
            context.window_manager.fileselect_add(self)
            return {"RUNNING_MODAL"}
        else:
            return self.execute(context)
    def execute(self,context):
        print("self.directory:",self.directory)
        db.cx.add_path(self.directory)
        return {"FINISHED"}


@_
class MATLIB_MT_path_menu(bpy.types.Menu):
    bl_label = "Add/Change Library"
    bl_description = "Choose/add Library Paths"
    def draw(self,context):
        layout = self.layout
        ap = db.cx.active_path
        for oid,path in db.cx.paths:
            layout.operator(
                    "matlib.select_path",
                    text=path,
                    icon=["FILE_FOLDER","BOOKMARKS"][oid==ap]).path_id = oid
        layout.separator()
        layout.operator("matlib.add_path").directory = ""


@_
class MATLIB_MT_mats_menu(bpy.types.Menu):
    bl_label = "Material Selector"
    bl_description = "Menu of Materials"
    def draw(self,context):
        i = -1
        for i,mat in db.cx.materials:
            self.layout.operator("matlib.load_material",text=mat,icon=["TRIA_RIGHT","FF"][mat in bpy.data.materials]).mat_id = i
        if i == -1 and db.cx.active_path:
            self.layout.label(text="No materials found in any blends in path:%s!"%db.cx.path(db.cx.active_path))


@_
class MATLIB_MT_main_menu(bpy.types.Menu):
    bl_label = "Librarian"
    bl_description = "MatLib Main Menu"
    @classmethod
    def poll(self,context):
        return (
            (
                hasattr(context.area.spaces.active,"context") and
                context.area.spaces.active.context == "MATERIAL"
            ) or
            (
                context.area.ui_type == "ShaderNodeTree"
            )
        )

    def draw(self,context):
        if context.material:
            has_name = context.material.name in db.cx.material_names()
        else:
            has_name = False
        op = self.layout.operator(
                "matlib.send_material",
                emboss=not has_name,
                icon=["FORWARD","FILE_TICK"][has_name])
        self.layout.menu(
                "MATLIB_MT_mats_menu",
                icon="MATERIAL")
        self.layout.menu(
                "MATLIB_MT_path_menu",
                icon="FILEBROWSER")


def prop_header_draw(self,context):
    if context.area.spaces.active.context == "MATERIAL":
        layout = self.layout.row(align=True)
        layout.menu("MATLIB_MT_main_menu",text="",icon="THREE_DOTS")

def node_header_draw(self,context):
    layout = self.layout.row(align=True)
    layout.menu("MATLIB_MT_main_menu",text="",icon="THREE_DOTS")

def register():
    list(map(bpy.utils.register_class,_()))
    # bpy.types.PROPERTIES_PT_navigation_bar.append(prop_header_draw)
    bpy.types.PROPERTIES_HT_header.append(prop_header_draw)
    bpy.types.NODE_HT_header.append(node_header_draw)
    ap = db.cx.active_path
    if ap:
        db.cx.prune_gone_blends(ap)
        db.cx.commit()

def unregister():
    # bpy.types.PROPERTIES_PT_navigation_bar.remove(prop_header_draw)
    bpy.types.NODE_HT_header.remove(node_header_draw)
    list(map(bpy.utils.unregister_class,_()))

