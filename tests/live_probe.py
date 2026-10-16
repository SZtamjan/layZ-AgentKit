import bpy
result = {
    'repos':[{'module':r.module,'directory':r.directory,'enabled':r.enabled} for r in bpy.context.preferences.extensions.repos],
    'install_properties':[{'id':p.identifier,'type':p.type} for p in bpy.ops.extensions.package_install_files.get_rna_type().properties],
    'saved_filepath':bpy.data.filepath,
    'objects':[o.name for o in bpy.context.scene.objects],
}
