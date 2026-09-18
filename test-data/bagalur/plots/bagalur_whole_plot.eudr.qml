<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.44" styleCategories="Symbology|Labeling">
  <renderer-v2 type="singleSymbol">
    <symbols>
      <symbol type="fill" name="0" alpha="1">
        <layer class="SimpleFill">
          <Option type="Map">
            <Option type="QString" name="color" value="0,0,0,0"/>
            <Option type="QString" name="outline_color" value="255,40,40,255"/>
            <Option type="QString" name="outline_width" value="0.7"/>
            <Option type="QString" name="outline_width_unit" value="MM"/>
            <Option type="QString" name="style" value="solid"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
  </renderer-v2>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="replace(&quot;ProductionPlace&quot;,'BAGALUR-','') || '\n' || format_number(&quot;Area&quot;,2) || ' ha'" isExpression="1" fontSize="9" textColor="255,255,255,255" fontWeight="75">
        <text-buffer bufferDraw="1" bufferSize="0.8" bufferColor="0,0,0,255"/>
      </text-style>
      <placement placement="1"/>
      <rendering scaleVisibility="0"/>
    </settings>
  </labeling>
</qgis>
