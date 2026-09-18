<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.44" styleCategories="AllStyleCategories">
  <pipe>
    <provider>
      <resampling enabled="true" zoomedInResamplingMethod="bilinear" zoomedOutResamplingMethod="average" maxOversampling="2"/>
    </provider>
    <rasterrenderer type="multibandcolor" redBand="1" greenBand="2" blueBand="3" alphaBand="-1" opacity="1" nodataColor="">
      <rasterTransparency/>
    </rasterrenderer>
    <brightnesscontrast brightness="0" contrast="0" gamma="1"/>
    <huesaturation saturation="0" grayscaleMode="0" colorizeOn="0" colorizeStrength="100" colorizeRed="255" colorizeGreen="128" colorizeBlue="128" invertColors="0"/>
    <rasterresampler maxOversampling="2" zoomedInResampler="bilinear" zoomedOutResampler="bilinear"/>
    <resamplingStage>provider</resamplingStage>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
