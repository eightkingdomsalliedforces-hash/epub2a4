# Chaquopy accesses callback methods from Python by reflection.
-keepclassmembers class * {
    public *** onProgress(int, java.lang.String);
    public boolean isCancelled();
}
