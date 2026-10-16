using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

public static class AgentKitValidation
{
    [Serializable] public class Fixture { public string assetPath; public int triangles; public Vector3 dimensions; }
    [Serializable] public class Input { public Fixture[] fixtures; }
    [Serializable] public class Result { public bool ok; public string unity; public List<string> passed = new List<string>(); public string error; }

    public static void Run()
    {
        string root = Directory.GetParent(Application.dataPath).FullName;
        var result = new Result { unity = Application.unityVersion };
        try
        {
            var input = JsonUtility.FromJson<Input>(File.ReadAllText(Path.Combine(root, "fixtures.json")));
            foreach (var fixture in input.fixtures)
            {
                AssetDatabase.ImportAsset(fixture.assetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                var model = AssetDatabase.LoadAssetAtPath<GameObject>(fixture.assetPath);
                if (model == null) throw new Exception("Model did not import: " + fixture.assetPath);
                var instance = UnityEngine.Object.Instantiate(model);
                try
                {
                    int triangles = 0;
                    foreach (var filter in instance.GetComponentsInChildren<MeshFilter>())
                        if (filter.sharedMesh != null) triangles += filter.sharedMesh.triangles.Length / 3;
                    if (triangles != fixture.triangles) throw new Exception("Triangle count mismatch: " + fixture.assetPath);
                    result.passed.Add(fixture.assetPath + ": mesh and triangle count");
                    var renderers = instance.GetComponentsInChildren<Renderer>();
                    if (renderers.Length == 0) throw new Exception("Model has no renderers");
                    Bounds bounds = renderers[0].bounds;
                    foreach (var renderer in renderers) bounds.Encapsulate(renderer.bounds);
                    // Blender Z up becomes Unity Y up.
                    var expected = new Vector3(fixture.dimensions.x, fixture.dimensions.z, fixture.dimensions.y);
                    if ((bounds.size - expected).magnitude > 0.001f)
                        throw new Exception("Physical dimensions mismatch: " + bounds.size + " versus " + expected);
                    result.passed.Add(fixture.assetPath + ": physical dimensions in metres");
                    foreach (var renderer in renderers)
                        foreach (var material in renderer.sharedMaterials)
                            if (material == null) throw new Exception("Missing imported material");
                    result.passed.Add(fixture.assetPath + ": material slots imported");
                }
                finally { UnityEngine.Object.DestroyImmediate(instance); }
            }
            result.ok = true;
        }
        catch (Exception exception) { result.error = exception.ToString(); }
        File.WriteAllText(Path.Combine(root, "validation.json"), JsonUtility.ToJson(result, true));
        EditorApplication.Exit(result.ok ? 0 : 1);
    }
}
