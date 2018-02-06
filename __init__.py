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
        "name": "matlib",
        "description":"Librarian of Materials",
        "author":"dustractor@gmail.com",
        "version":(1,0),
        "blender":(2,78,0),
        "location":"appropriate",
        "warning":"",
        "wiki_url":"",
        "tracker_url":"https://github.com/dustractor/matlib.git",
        "category": "Material Library" }

import sqlite3
import pathlib
import bpy
import bpy.utils.previews
icons_d = bpy.utils.previews.new()
iconpath = str(pathlib.Path(__file__).parent/"file_save.png")
icons_d.load("file_save",iconpath,"IMAGE")

DBNAME = "matlibdata.sqlitedb"


class MaterialsLibrarian(sqlite3.Connection):

    def __init__(self,name,**kwargs):
        super().__init__(name,**kwargs)
        self.cu = self.cursor()
        self.cu.row_factory = lambda c,r:r[0]
        self.executescript(
        """ pragma foreign_keys=ON; pragma recursive_triggers=ON;

        create table if not exists paths (
        id integer primary key, name text, mtime real,
        unique (name) on conflict replace);

        create table if not exists blends (
        id integer primary key, path_id integer, name text, mtime real,
        unique (name) on conflict replace,
        foreign key (path_id) references paths(id) on delete cascade);

        create table if not exists materials (
        id integer primary key, blend_id integer, name text,
        unique (name) on conflict replace,
        foreign key (blend_id) references blends(id) on delete cascade);

        create table if not exists active_path (
        state integer default 0, path_id integer,
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
                    bpy.utils.user_resource("CONFIG",path=DBNAME),
                    factory=MaterialsLibrarian)
        return self._handle


db = MaterialsLibrary()


class MATLIB_OT_send_material(bpy.types.Operator):

    bl_idname = "matlib.send_material"
    bl_label = "Send Material"
    bl_description = "Send current material to the library"
    bl_options = {"INTERNAL"}

    force_overwrite = bpy.props.BoolProperty(
            default=False,
            name="Overwrite existing Material?",
            description="Check this box and choose OK to overwrite the "
                        "previously existing material of same name.")
    matfile = bpy.props.StringProperty(default="",
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
        path = db.cx.cu.execute("select name from paths where id=?",(path_id,)
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


class MATLIB_OT_load_material(bpy.types.Operator):
    bl_idname = "matlib.load_material"
    bl_label = "Load Material"
    bl_options = {"INTERNAL"}
    mat_id = bpy.props.IntProperty()

    def execute(self,context):
        print("loading material",self.mat_id)
        blend,matname = db.cx.execute(
                """select blends.name,materials.name from materials
                join blends on blends.id=materials.blend_id
                where materials.id=? """,
                (self.mat_id,)).fetchone()
        with bpy.data.libraries.load(blend) as (data_from,data_to):
            data_to.materials = [matname]
        if context.material_slot:
            context.material_slot.material = data_to.materials[0]
        return {"FINISHED"}


class MATLIB_OT_select_path(bpy.types.Operator):
    bl_idname = "matlib.select_path"
    bl_label = "Select Path"
    bl_options = {"INTERNAL"}
    bl_description = "hold shift to open in file browser"

    path_id = bpy.props.IntProperty()

    def invoke(self,context,event):
        if event.shift:
            path = db.cx.path(self.path_id)
            if path:
                bpy.ops.wm.path_open(filepath=path)
                return {"FINISHED"}
            else:
                return {"CANCELLED"}
        return self.execute(context)

    def execute(self,context):
        print("selecting path",self.path_id)
        db.cx.active_path = self.path_id
        return {"FINISHED"}


class MATLIB_OT_add_path(bpy.types.Operator):
    bl_idname = "matlib.add_path"
    bl_label = "Add Path..."
    bl_options = {"INTERNAL"}
    directory = bpy.props.StringProperty(
            subtype="DIR_PATH",maxlen=1024,default="")

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


class MatLib(bpy.types.PropertyGroup):

    def display(self,context,layout):
        row = layout.row()
        row.label(" ",icon="BLANK1")
        subrow = row.row(align=True)
        subrow.operator(
                "matlib.send_material",
                text="",
                icon_value=icons_d["file_save"].icon_id)
        prefs = context.user_preferences.addons[__name__].preferences
        ap = db.cx.active_path
        if not prefs.hide_path_option or (ap==None):
            subrow.menu("MATLIB_MT_path_menu",text="",
                    icon=["FILE_FOLDER","BOOKMARKS"][ap!=None])
        row.menu("MATLIB_MT_mats_menu",text="",icon="MATERIAL_DATA")


class MATLIB_MT_path_menu(bpy.types.Menu):
    bl_label = "Library Path Selector"
    bl_description = "Choose/add Library Paths"

    def draw(self,context):
        layout = self.layout
        ap = db.cx.active_path
        for oid,path in db.cx.paths:
            layout.operator("matlib.select_path",text=path,
                    icon=["BLANK1","FILE_TICK"][oid==ap]).path_id = oid
        layout.separator()
        layout.operator("matlib.add_path").directory = ""


class MATLIB_MT_mats_menu(bpy.types.Menu):
    bl_label = "Material Selector"
    bl_description = "Menu of Materials"

    def draw(self,context):
        for i,mat in db.cx.materials:
            self.layout.operator("matlib.load_material",text=mat).mat_id = i


class MATLIB_PT_panel(bpy.types.Panel):
    bl_label = "matlib"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"

    @classmethod
    def poll(self,context):
        prefs = context.user_preferences.addons[__name__].preferences
        return prefs.displaymode == "PANEL"

    def draw(self,context):
        context.window_manager.matlib.display(context,self.layout)


class MatLibPrefs(bpy.types.AddonPreferences):
    bl_idname = __name__

    hide_path_option = bpy.props.BoolProperty(
            name="Hide the Path Selector",
            description="Don't display the path menu once one has been set.",
            default=False)

    displaymode = bpy.props.EnumProperty(
            name="Interface Display Mode",
            description="UI can be shown above, below or panel",
            items=(
        ("PANEL","Materials Panel","a panel in material properties"),
        ("ABOVE","Above Material Selector","above the materials selector"),
        ("BELOW","Below Material Selector","below the materials selector")),
            default="ABOVE")

    def draw(self,context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.scale_x,row.scale_y = [2,2]
        row.label("Interface Options:")
        box.prop(self,"displaymode")
        box.prop(self,"hide_path_option")
        if self.hide_path_option:
            box.menu("MATLIB_MT_path_menu")

_classes = [
    MatLibPrefs, MatLib, MATLIB_PT_panel,
    MATLIB_OT_send_material, MATLIB_OT_load_material,
    MATLIB_OT_select_path, MATLIB_OT_add_path,
    MATLIB_MT_path_menu, MATLIB_MT_mats_menu ]

def register():
    list(map(bpy.utils.register_class,_classes))
    bpy.types.WindowManager.matlib = bpy.props.PointerProperty(type=MatLib)
    prefs = bpy.context.user_preferences.addons[__name__].preferences
    if prefs.displaymode == "ABOVE":
        bpy.types.CYCLES_PT_context_material.prepend(MATLIB_PT_panel.draw)
    elif prefs.displaymode == "BELOW":
        bpy.types.CYCLES_PT_context_material.append(MATLIB_PT_panel.draw)
    ap = db.cx.active_path
    if ap:
        db.cx.prune_gone_blends(ap)
        db.cx.commit()

def unregister():
    try:
        bpy.types.CYCLES_PT_context_material.remove(MATLIB_PT_panel.draw)
    except:
        pass
    del bpy.types.WindowManager.matlib
    list(map(bpy.utils.unregister_class,_classes))

