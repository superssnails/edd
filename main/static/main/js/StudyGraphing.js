// File last modified on: Wed Dec 21 2016 14:53:35  
/// <reference path="../typings/d3/d3.d.ts"/>;
/// <reference path="GraphHelperMethods.ts" />
/// <reference path="StudyGraphingHelperMethods.ts" />
var StudyDGraphing;
StudyDGraphing = {
    Setup: function (graphdiv) {
        if (graphdiv) {
            this.graphDiv = $("#" + graphdiv);
        }
        else {
            this.graphDiv = $("#graphDiv");
        }
    },
    clearAllSets: function () {
        $('.tooMuchData').remove();
        var divs = this.graphDiv.siblings();
        if ($(divs[1]).find("svg").length == 0) {
            d3.selectAll("svg").remove();
        }
        else {
            for (var div = 1; div < divs.length; div++) {
                $(divs[div]).find("svg").remove();
            }
        }
    },
    addNewSet: function (newSet, type) {
        var buttonArr = StudyHelper.getButtonElement(this.graphDiv), selector = StudyHelper.getSelectorElement(this.graphDiv), type = StudyHelper.measurementType(type), buttons = {
            'line': buttonArr[0],
            'bar-empty': buttonArr[1],
            'bar-time': buttonArr[2],
            'bar-line': buttonArr[3],
            'bar-measurement': buttonArr[4]
        }, selectors = {
            'line': selector[1],
            'bar-time': selector[2],
            'bar-line': selector[3],
            'bar-measurement': selector[4]
        };
        /**
         * display grouped bar chart by measurement if most of the measurement types are protocol
         *  currently commented out because this is buggy
        **/
        //StudyHelper.showProteomicGraph(type, selectors, 'bar-measurement', buttons);
        //line chart
        $(buttons['line']).click(function (event) {
            event.preventDefault();
            StudyHelper.displayGraph(selectors, 'line');
            $('label.btn').removeClass('active');
            $(this).addClass('active');
            //hide graph option buttons
            $(buttons['bar-time']).addClass('hidden');
            $(buttons['bar-line']).addClass('hidden');
            $(buttons['bar-measurement']).addClass('hidden');
            return false;
        });
        // when user clicks bar button, show option buttons
        $(buttons['bar-empty']).click(function (event) {
            event.preventDefault();
            $(buttons['bar-time']).removeClass('hidden');
            $(buttons['bar-line']).removeClass('hidden');
            $(buttons['bar-measurement']).removeClass('hidden');
            $('label.btn').removeClass('active');
            $(this).addClass('active');
            return false;
        });
        //bar chart grouped by time
        $(buttons['bar-time']).click(function (event) {
            var rects = d3.selectAll('.barTime rect')[0];
            StudyHelper.buttonEventHandler(newSet, event, rects, 'bar-time', selectors, buttonArr);
        });
        //bar chart grouped by line name
        $(buttons['bar-line']).click(function (event) {
            var rects = d3.selectAll('.barAssay rect')[0];
            StudyHelper.buttonEventHandler(newSet, event, rects, 'bar-line', selectors, buttonArr);
        });
        //bar chart grouped by measurement
        $(buttons['bar-measurement']).click(function (event) {
            var rects = d3.selectAll('.barMeasurement rect')[0];
            StudyHelper.buttonEventHandler(newSet, event, rects, 'bar-measurement', selectors, buttonArr);
        });
        var barAssayObj = GraphHelperMethods.concatAssays(newSet);
        //data for graphs
        var graphSet = {
            barAssayObj: GraphHelperMethods.concatAssays(newSet),
            create_x_axis: GraphHelperMethods.createXAxis,
            create_right_y_axis: GraphHelperMethods.createRightYAxis,
            create_y_axis: GraphHelperMethods.createLeftYAxis,
            x_axis: GraphHelperMethods.make_x_axis,
            y_axis: GraphHelperMethods.make_right_y_axis,
            individualData: newSet,
            assayMeasurements: barAssayObj,
            width: 750,
            height: 220
        };
        //render different graphs
        createMultiLineGraph(graphSet, GraphHelperMethods.createSvg(selector[1]));
        createGroupedBarGraph(graphSet, GraphHelperMethods.createSvg(selector[2]), 'x');
        createGroupedBarGraph(graphSet, GraphHelperMethods.createSvg(selector[3]), 'name');
        createGroupedBarGraph(graphSet, GraphHelperMethods.createSvg(selector[4]), 'measurement');
        //rectangle selectors for each bar svg.
        var rectAssayBar = d3.selectAll('.barAssay rect')[0];
        var rectMeasBar = d3.selectAll('.barMeasurement rect')[0];
        var rectTimeBar = d3.selectAll('.barTime rect')[0];
        //make sure there is a message to display - please filter - if there are no bars showing on bar graph. 
        if ($(selector[2]).css('display') === 'block') {
            StudyHelper.svgWidth(selector[2], rectTimeBar);
        }
        if ($(selector[3]).css('display') === 'block') {
            StudyHelper.svgWidth(selector[3], rectAssayBar);
        }
        if ($(selector[4]).css('display') === 'block') {
            StudyHelper.svgWidth(selector[4], rectMeasBar);
        }
        if (!newSet.label) {
            $('#debug').text('Failed to fetch series.');
            return;
        }
    },
};
//# sourceMappingURL=data:application/json;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU3R1ZHlHcmFwaGluZy5qcyIsInNvdXJjZVJvb3QiOiIiLCJzb3VyY2VzIjpbIlN0dWR5R3JhcGhpbmcudHMiXSwibmFtZXMiOltdLCJtYXBwaW5ncyI6IkFBQUEsb0RBQW9EO0FBQ3BELDhDQUE4QztBQUM5Qyw4Q0FBOEM7QUFDOUMsc0RBQXNEO0FBRXRELElBQUksY0FBa0IsQ0FBQztBQUt2QixjQUFjLEdBQUc7SUFFaEIsS0FBSyxFQUFDLFVBQVMsUUFBUTtRQUVoQixFQUFFLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDO1lBQ3BCLElBQUksQ0FBQyxRQUFRLEdBQUcsQ0FBQyxDQUFDLEdBQUcsR0FBRyxRQUFRLENBQUMsQ0FBQztRQUNuQyxDQUFDO1FBQUMsSUFBSSxDQUFDLENBQUM7WUFDUCxJQUFJLENBQUMsUUFBUSxHQUFHLENBQUMsQ0FBQyxXQUFXLENBQUMsQ0FBQztRQUMxQixDQUFDO0lBQ1IsQ0FBQztJQUVELFlBQVksRUFBQztRQUNOLENBQUMsQ0FBQyxjQUFjLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUMzQixJQUFJLElBQUksR0FBSSxJQUFJLENBQUMsUUFBUSxDQUFDLFFBQVEsRUFBRSxDQUFDO1FBRXJDLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxJQUFJLENBQUUsS0FBSyxDQUFFLENBQUMsTUFBTSxJQUFJLENBQUUsQ0FBQyxDQUFBLENBQUM7WUFDdEMsRUFBRSxDQUFDLFNBQVMsQ0FBQyxLQUFLLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQztRQUNsQyxDQUFDO1FBQ0QsSUFBSSxDQUFDLENBQUM7WUFDRixHQUFHLENBQUMsQ0FBQyxJQUFJLEdBQUcsR0FBRyxDQUFDLEVBQUUsR0FBRyxHQUFHLElBQUksQ0FBQyxNQUFNLEVBQUUsR0FBRyxFQUFFLEVBQUUsQ0FBQztnQkFDekMsQ0FBQyxDQUFDLElBQUksQ0FBQyxHQUFHLENBQUMsQ0FBQyxDQUFDLElBQUksQ0FBQyxLQUFLLENBQUMsQ0FBQyxNQUFNLEVBQUUsQ0FBQTtZQUNyQyxDQUFDO1FBQ0wsQ0FBQztJQUNSLENBQUM7SUFFRCxTQUFTLEVBQUMsVUFBUyxNQUFNLEVBQUUsSUFBSTtRQUV4QixJQUFJLFNBQVMsR0FBRyxXQUFXLENBQUMsZ0JBQWdCLENBQUMsSUFBSSxDQUFDLFFBQVEsQ0FBQyxFQUN2RCxRQUFRLEdBQUcsV0FBVyxDQUFDLGtCQUFrQixDQUFDLElBQUksQ0FBQyxRQUFRLENBQUMsRUFDeEQsSUFBSSxHQUFHLFdBQVcsQ0FBQyxlQUFlLENBQUMsSUFBSSxDQUFDLEVBQ3hDLE9BQU8sR0FBRztZQUNOLE1BQU0sRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDO1lBQ3BCLFdBQVcsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDO1lBQ3pCLFVBQVUsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDO1lBQ3hCLFVBQVUsRUFBRSxTQUFTLENBQUMsQ0FBQyxDQUFDO1lBQ3hCLGlCQUFpQixFQUFFLFNBQVMsQ0FBQyxDQUFDLENBQUM7U0FDbEMsRUFDRCxTQUFTLEdBQUc7WUFDUixNQUFNLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQztZQUNuQixVQUFVLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQztZQUN2QixVQUFVLEVBQUUsUUFBUSxDQUFDLENBQUMsQ0FBQztZQUN2QixpQkFBaUIsRUFBRSxRQUFRLENBQUMsQ0FBQyxDQUFDO1NBQ2pDLENBQUM7UUFFTjs7O1dBR0c7UUFDSCw4RUFBOEU7UUFFOUUsWUFBWTtRQUNaLENBQUMsQ0FBQyxPQUFPLENBQUMsTUFBTSxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsVUFBUyxLQUFLO1lBQ25DLEtBQUssQ0FBQyxjQUFjLEVBQUUsQ0FBQztZQUN2QixXQUFXLENBQUMsWUFBWSxDQUFDLFNBQVMsRUFBRSxNQUFNLENBQUMsQ0FBQztZQUM1QyxDQUFDLENBQUMsV0FBVyxDQUFDLENBQUMsV0FBVyxDQUFDLFFBQVEsQ0FBQyxDQUFDO1lBQ3JDLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUM7WUFFM0IsMkJBQTJCO1lBQzNCLENBQUMsQ0FBQyxPQUFPLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUM7WUFDMUMsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxRQUFRLENBQUMsQ0FBQztZQUMxQyxDQUFDLENBQUMsT0FBTyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUM7WUFDakQsTUFBTSxDQUFDLEtBQUssQ0FBQTtRQUNoQixDQUFDLENBQUMsQ0FBQztRQUVILG1EQUFtRDtRQUNuRCxDQUFDLENBQUMsT0FBTyxDQUFDLFdBQVcsQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLFVBQVMsS0FBSztZQUN4QyxLQUFLLENBQUMsY0FBYyxFQUFFLENBQUM7WUFDdkIsQ0FBQyxDQUFDLE9BQU8sQ0FBQyxVQUFVLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxRQUFRLENBQUMsQ0FBQztZQUM3QyxDQUFDLENBQUMsT0FBTyxDQUFDLFVBQVUsQ0FBQyxDQUFDLENBQUMsV0FBVyxDQUFDLFFBQVEsQ0FBQyxDQUFDO1lBQzdDLENBQUMsQ0FBQyxPQUFPLENBQUMsaUJBQWlCLENBQUMsQ0FBQyxDQUFDLFdBQVcsQ0FBQyxRQUFRLENBQUMsQ0FBQztZQUNwRCxDQUFDLENBQUMsV0FBVyxDQUFDLENBQUMsV0FBVyxDQUFDLFFBQVEsQ0FBQyxDQUFDO1lBQ3JDLENBQUMsQ0FBQyxJQUFJLENBQUMsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUM7WUFDM0IsTUFBTSxDQUFDLEtBQUssQ0FBQTtRQUNoQixDQUFDLENBQUMsQ0FBQztRQUVILDJCQUEyQjtRQUMzQixDQUFDLENBQUMsT0FBTyxDQUFDLFVBQVUsQ0FBQyxDQUFDLENBQUMsS0FBSyxDQUFDLFVBQVMsS0FBSztZQUN2QyxJQUFJLEtBQUssR0FBRyxFQUFFLENBQUMsU0FBUyxDQUFDLGVBQWUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1lBQzdDLFdBQVcsQ0FBQyxrQkFBa0IsQ0FBQyxNQUFNLEVBQUUsS0FBSyxFQUFFLEtBQUssRUFBRSxVQUFVLEVBQUUsU0FBUyxFQUFFLFNBQVMsQ0FBQyxDQUFDO1FBQzNGLENBQUMsQ0FBQyxDQUFDO1FBRUgsZ0NBQWdDO1FBQ2hDLENBQUMsQ0FBQyxPQUFPLENBQUMsVUFBVSxDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsVUFBUyxLQUFLO1lBQ3ZDLElBQUksS0FBSyxHQUFHLEVBQUUsQ0FBQyxTQUFTLENBQUMsZ0JBQWdCLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUM5QyxXQUFXLENBQUMsa0JBQWtCLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsVUFBVSxFQUFFLFNBQVMsRUFBRSxTQUFTLENBQUMsQ0FBQztRQUMzRixDQUFDLENBQUMsQ0FBQztRQUVILGtDQUFrQztRQUNsQyxDQUFDLENBQUMsT0FBTyxDQUFDLGlCQUFpQixDQUFDLENBQUMsQ0FBQyxLQUFLLENBQUMsVUFBUyxLQUFLO1lBQzlDLElBQUksS0FBSyxHQUFHLEVBQUUsQ0FBQyxTQUFTLENBQUMsc0JBQXNCLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQztZQUNwRCxXQUFXLENBQUMsa0JBQWtCLENBQUMsTUFBTSxFQUFFLEtBQUssRUFBRSxLQUFLLEVBQUUsaUJBQWlCLEVBQUUsU0FBUyxFQUFFLFNBQVMsQ0FBQyxDQUFDO1FBQ2xHLENBQUMsQ0FBQyxDQUFDO1FBRUgsSUFBSSxXQUFXLEdBQUksa0JBQWtCLENBQUMsWUFBWSxDQUFDLE1BQU0sQ0FBQyxDQUFDO1FBRTNELGlCQUFpQjtRQUNqQixJQUFJLFFBQVEsR0FBRztZQUNYLFdBQVcsRUFBRSxrQkFBa0IsQ0FBQyxZQUFZLENBQUMsTUFBTSxDQUFDO1lBQ3BELGFBQWEsRUFBRSxrQkFBa0IsQ0FBQyxXQUFXO1lBQzdDLG1CQUFtQixFQUFFLGtCQUFrQixDQUFDLGdCQUFnQjtZQUN4RCxhQUFhLEVBQUUsa0JBQWtCLENBQUMsZUFBZTtZQUNqRCxNQUFNLEVBQUUsa0JBQWtCLENBQUMsV0FBVztZQUN0QyxNQUFNLEVBQUUsa0JBQWtCLENBQUMsaUJBQWlCO1lBQzVDLGNBQWMsRUFBRSxNQUFNO1lBQ3RCLGlCQUFpQixFQUFFLFdBQVc7WUFDOUIsS0FBSyxFQUFFLEdBQUc7WUFDVixNQUFNLEVBQUUsR0FBRztTQUNkLENBQUM7UUFFRix5QkFBeUI7UUFDekIsb0JBQW9CLENBQUMsUUFBUSxFQUFFLGtCQUFrQixDQUFDLFNBQVMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQzFFLHFCQUFxQixDQUFDLFFBQVEsRUFBRSxrQkFBa0IsQ0FBQyxTQUFTLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxDQUFDLEVBQUUsR0FBRyxDQUFDLENBQUM7UUFDaEYscUJBQXFCLENBQUMsUUFBUSxFQUFFLGtCQUFrQixDQUFDLFNBQVMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDLENBQUMsRUFBRSxNQUFNLENBQUMsQ0FBQztRQUNuRixxQkFBcUIsQ0FBQyxRQUFRLEVBQUUsa0JBQWtCLENBQUMsU0FBUyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUMsQ0FBQyxFQUFFLGFBQWEsQ0FBQyxDQUFDO1FBRTFGLHVDQUF1QztRQUN2QyxJQUFJLFlBQVksR0FBRyxFQUFFLENBQUMsU0FBUyxDQUFDLGdCQUFnQixDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFDckQsSUFBSSxXQUFXLEdBQUcsRUFBRSxDQUFDLFNBQVMsQ0FBQyxzQkFBc0IsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDO1FBQzFELElBQUksV0FBVyxHQUFHLEVBQUUsQ0FBQyxTQUFTLENBQUMsZUFBZSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUM7UUFFbkQsdUdBQXVHO1FBQ3ZHLEVBQUUsQ0FBQyxDQUFDLENBQUMsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDLENBQUMsQ0FBQyxHQUFHLENBQUMsU0FBUyxDQUFDLEtBQUssT0FBTyxDQUFDLENBQUMsQ0FBQztZQUMzQyxXQUFXLENBQUMsUUFBUSxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUMsRUFBRSxXQUFXLENBQUMsQ0FBQztRQUNwRCxDQUFDO1FBQ0QsRUFBRSxDQUFDLENBQUMsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxDQUFDLENBQUMsQ0FBQyxDQUFDLEdBQUcsQ0FBQyxTQUFTLENBQUMsS0FBSyxPQUFPLENBQUMsQ0FBQyxDQUFDO1lBQzNDLFdBQVcsQ0FBQyxRQUFRLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxFQUFFLFlBQVksQ0FBQyxDQUFDO1FBQ3JELENBQUM7UUFDRCxFQUFFLENBQUMsQ0FBQyxDQUFDLENBQUMsUUFBUSxDQUFDLENBQUMsQ0FBQyxDQUFDLENBQUMsR0FBRyxDQUFDLFNBQVMsQ0FBQyxLQUFLLE9BQU8sQ0FBQyxDQUFDLENBQUM7WUFDM0MsV0FBVyxDQUFDLFFBQVEsQ0FBQyxRQUFRLENBQUMsQ0FBQyxDQUFDLEVBQUUsV0FBVyxDQUFDLENBQUM7UUFDcEQsQ0FBQztRQUNQLEVBQUUsQ0FBQyxDQUFDLENBQUMsTUFBTSxDQUFDLEtBQUssQ0FBQyxDQUFDLENBQUM7WUFDbkIsQ0FBQyxDQUFDLFFBQVEsQ0FBQyxDQUFDLElBQUksQ0FBQyx5QkFBeUIsQ0FBQyxDQUFDO1lBQzVDLE1BQU0sQ0FBQztRQUNSLENBQUM7SUFDRixDQUFDO0NBRUQsQ0FBQyIsInNvdXJjZXNDb250ZW50IjpbIi8vIEZpbGUgbGFzdCBtb2RpZmllZCBvbjogV2VkIERlYyAyMSAyMDE2IDE0OjUzOjM1ICBcbi8vLyA8cmVmZXJlbmNlIHBhdGg9XCIuLi90eXBpbmdzL2QzL2QzLmQudHNcIi8+O1xuLy8vIDxyZWZlcmVuY2UgcGF0aD1cIkdyYXBoSGVscGVyTWV0aG9kcy50c1wiIC8+XG4vLy8gPHJlZmVyZW5jZSBwYXRoPVwiU3R1ZHlHcmFwaGluZ0hlbHBlck1ldGhvZHMudHNcIiAvPlxuXG52YXIgU3R1ZHlER3JhcGhpbmc6YW55O1xuXG5kZWNsYXJlIHZhciBjcmVhdGVNdWx0aUxpbmVHcmFwaDtcbmRlY2xhcmUgdmFyIGNyZWF0ZUdyb3VwZWRCYXJHcmFwaDtcblxuU3R1ZHlER3JhcGhpbmcgPSB7XG5cblx0U2V0dXA6ZnVuY3Rpb24oZ3JhcGhkaXYpIHtcblxuICAgICAgICBpZiAoZ3JhcGhkaXYpIHtcblx0XHRcdHRoaXMuZ3JhcGhEaXYgPSAkKFwiI1wiICsgZ3JhcGhkaXYpO1xuXHRcdH0gZWxzZSB7XG5cdFx0XHR0aGlzLmdyYXBoRGl2ID0gJChcIiNncmFwaERpdlwiKTtcbiAgICAgICAgfVxuXHR9LFxuXG5cdGNsZWFyQWxsU2V0czpmdW5jdGlvbigpIHtcbiAgICAgICAgJCgnLnRvb011Y2hEYXRhJykucmVtb3ZlKCk7XG4gICAgICAgIHZhciBkaXZzID0gIHRoaXMuZ3JhcGhEaXYuc2libGluZ3MoKTtcblxuICAgICAgICBpZiAoJChkaXZzWzFdKS5maW5kKCBcInN2Z1wiICkubGVuZ3RoID09IDAgKXtcbiAgICAgICAgICAgICBkMy5zZWxlY3RBbGwoXCJzdmdcIikucmVtb3ZlKCk7XG4gICAgICAgIH1cbiAgICAgICAgZWxzZSB7XG4gICAgICAgICAgICBmb3IgKHZhciBkaXYgPSAxOyBkaXYgPCBkaXZzLmxlbmd0aDsgZGl2KyspIHtcbiAgICAgICAgICAgICAgICAkKGRpdnNbZGl2XSkuZmluZChcInN2Z1wiKS5yZW1vdmUoKVxuICAgICAgICAgICAgfVxuICAgICAgICB9XG5cdH0sXG5cblx0YWRkTmV3U2V0OmZ1bmN0aW9uKG5ld1NldCwgdHlwZSkge1xuXG4gICAgICAgIHZhciBidXR0b25BcnIgPSBTdHVkeUhlbHBlci5nZXRCdXR0b25FbGVtZW50KHRoaXMuZ3JhcGhEaXYpLFxuICAgICAgICAgICAgc2VsZWN0b3IgPSBTdHVkeUhlbHBlci5nZXRTZWxlY3RvckVsZW1lbnQodGhpcy5ncmFwaERpdiksXG4gICAgICAgICAgICB0eXBlID0gU3R1ZHlIZWxwZXIubWVhc3VyZW1lbnRUeXBlKHR5cGUpLFxuICAgICAgICAgICAgYnV0dG9ucyA9IHtcbiAgICAgICAgICAgICAgICAnbGluZSc6IGJ1dHRvbkFyclswXSxcbiAgICAgICAgICAgICAgICAnYmFyLWVtcHR5JzogYnV0dG9uQXJyWzFdLFxuICAgICAgICAgICAgICAgICdiYXItdGltZSc6IGJ1dHRvbkFyclsyXSxcbiAgICAgICAgICAgICAgICAnYmFyLWxpbmUnOiBidXR0b25BcnJbM10sXG4gICAgICAgICAgICAgICAgJ2Jhci1tZWFzdXJlbWVudCc6IGJ1dHRvbkFycls0XVxuICAgICAgICAgICAgfSxcbiAgICAgICAgICAgIHNlbGVjdG9ycyA9IHtcbiAgICAgICAgICAgICAgICAnbGluZSc6IHNlbGVjdG9yWzFdLFxuICAgICAgICAgICAgICAgICdiYXItdGltZSc6IHNlbGVjdG9yWzJdLFxuICAgICAgICAgICAgICAgICdiYXItbGluZSc6IHNlbGVjdG9yWzNdLFxuICAgICAgICAgICAgICAgICdiYXItbWVhc3VyZW1lbnQnOiBzZWxlY3Rvcls0XVxuICAgICAgICAgICAgfTtcblxuICAgICAgICAvKipcbiAgICAgICAgICogZGlzcGxheSBncm91cGVkIGJhciBjaGFydCBieSBtZWFzdXJlbWVudCBpZiBtb3N0IG9mIHRoZSBtZWFzdXJlbWVudCB0eXBlcyBhcmUgcHJvdG9jb2xcbiAgICAgICAgICogIGN1cnJlbnRseSBjb21tZW50ZWQgb3V0IGJlY2F1c2UgdGhpcyBpcyBidWdneVxuICAgICAgICAqKi9cbiAgICAgICAgLy9TdHVkeUhlbHBlci5zaG93UHJvdGVvbWljR3JhcGgodHlwZSwgc2VsZWN0b3JzLCAnYmFyLW1lYXN1cmVtZW50JywgYnV0dG9ucyk7XG5cbiAgICAgICAgLy9saW5lIGNoYXJ0XG4gICAgICAgICQoYnV0dG9uc1snbGluZSddKS5jbGljayhmdW5jdGlvbihldmVudCkge1xuICAgICAgICAgICAgZXZlbnQucHJldmVudERlZmF1bHQoKTtcbiAgICAgICAgICAgIFN0dWR5SGVscGVyLmRpc3BsYXlHcmFwaChzZWxlY3RvcnMsICdsaW5lJyk7XG4gICAgICAgICAgICAkKCdsYWJlbC5idG4nKS5yZW1vdmVDbGFzcygnYWN0aXZlJyk7XG4gICAgICAgICAgICAkKHRoaXMpLmFkZENsYXNzKCdhY3RpdmUnKTtcblxuICAgICAgICAgICAgLy9oaWRlIGdyYXBoIG9wdGlvbiBidXR0b25zXG4gICAgICAgICAgICAkKGJ1dHRvbnNbJ2Jhci10aW1lJ10pLmFkZENsYXNzKCdoaWRkZW4nKTtcbiAgICAgICAgICAgICQoYnV0dG9uc1snYmFyLWxpbmUnXSkuYWRkQ2xhc3MoJ2hpZGRlbicpO1xuICAgICAgICAgICAgJChidXR0b25zWydiYXItbWVhc3VyZW1lbnQnXSkuYWRkQ2xhc3MoJ2hpZGRlbicpO1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlXG4gICAgICAgIH0pO1xuXG4gICAgICAgIC8vIHdoZW4gdXNlciBjbGlja3MgYmFyIGJ1dHRvbiwgc2hvdyBvcHRpb24gYnV0dG9uc1xuICAgICAgICAkKGJ1dHRvbnNbJ2Jhci1lbXB0eSddKS5jbGljayhmdW5jdGlvbihldmVudCl7XG4gICAgICAgICAgICBldmVudC5wcmV2ZW50RGVmYXVsdCgpO1xuICAgICAgICAgICAgJChidXR0b25zWydiYXItdGltZSddKS5yZW1vdmVDbGFzcygnaGlkZGVuJyk7XG4gICAgICAgICAgICAkKGJ1dHRvbnNbJ2Jhci1saW5lJ10pLnJlbW92ZUNsYXNzKCdoaWRkZW4nKTtcbiAgICAgICAgICAgICQoYnV0dG9uc1snYmFyLW1lYXN1cmVtZW50J10pLnJlbW92ZUNsYXNzKCdoaWRkZW4nKTtcbiAgICAgICAgICAgICQoJ2xhYmVsLmJ0bicpLnJlbW92ZUNsYXNzKCdhY3RpdmUnKTtcbiAgICAgICAgICAgICQodGhpcykuYWRkQ2xhc3MoJ2FjdGl2ZScpO1xuICAgICAgICAgICAgcmV0dXJuIGZhbHNlXG4gICAgICAgIH0pO1xuXG4gICAgICAgIC8vYmFyIGNoYXJ0IGdyb3VwZWQgYnkgdGltZVxuICAgICAgICAkKGJ1dHRvbnNbJ2Jhci10aW1lJ10pLmNsaWNrKGZ1bmN0aW9uKGV2ZW50KSB7XG4gICAgICAgICAgICB2YXIgcmVjdHMgPSBkMy5zZWxlY3RBbGwoJy5iYXJUaW1lIHJlY3QnKVswXTtcbiAgICAgICAgICAgIFN0dWR5SGVscGVyLmJ1dHRvbkV2ZW50SGFuZGxlcihuZXdTZXQsIGV2ZW50LCByZWN0cywgJ2Jhci10aW1lJywgc2VsZWN0b3JzLCBidXR0b25BcnIpO1xuICAgICAgICB9KTtcblxuICAgICAgICAvL2JhciBjaGFydCBncm91cGVkIGJ5IGxpbmUgbmFtZVxuICAgICAgICAkKGJ1dHRvbnNbJ2Jhci1saW5lJ10pLmNsaWNrKGZ1bmN0aW9uKGV2ZW50KSB7XG4gICAgICAgICAgICB2YXIgcmVjdHMgPSBkMy5zZWxlY3RBbGwoJy5iYXJBc3NheSByZWN0JylbMF07XG4gICAgICAgICAgICBTdHVkeUhlbHBlci5idXR0b25FdmVudEhhbmRsZXIobmV3U2V0LCBldmVudCwgcmVjdHMsICdiYXItbGluZScsIHNlbGVjdG9ycywgYnV0dG9uQXJyKTtcbiAgICAgICAgfSk7XG5cbiAgICAgICAgLy9iYXIgY2hhcnQgZ3JvdXBlZCBieSBtZWFzdXJlbWVudFxuICAgICAgICAkKGJ1dHRvbnNbJ2Jhci1tZWFzdXJlbWVudCddKS5jbGljayhmdW5jdGlvbihldmVudCkge1xuICAgICAgICAgICAgdmFyIHJlY3RzID0gZDMuc2VsZWN0QWxsKCcuYmFyTWVhc3VyZW1lbnQgcmVjdCcpWzBdO1xuICAgICAgICAgICAgU3R1ZHlIZWxwZXIuYnV0dG9uRXZlbnRIYW5kbGVyKG5ld1NldCwgZXZlbnQsIHJlY3RzLCAnYmFyLW1lYXN1cmVtZW50Jywgc2VsZWN0b3JzLCBidXR0b25BcnIpO1xuICAgICAgICB9KTtcblxuICAgICAgICB2YXIgYmFyQXNzYXlPYmogID0gR3JhcGhIZWxwZXJNZXRob2RzLmNvbmNhdEFzc2F5cyhuZXdTZXQpO1xuXG4gICAgICAgIC8vZGF0YSBmb3IgZ3JhcGhzXG4gICAgICAgIHZhciBncmFwaFNldCA9IHtcbiAgICAgICAgICAgIGJhckFzc2F5T2JqOiBHcmFwaEhlbHBlck1ldGhvZHMuY29uY2F0QXNzYXlzKG5ld1NldCksXG4gICAgICAgICAgICBjcmVhdGVfeF9heGlzOiBHcmFwaEhlbHBlck1ldGhvZHMuY3JlYXRlWEF4aXMsXG4gICAgICAgICAgICBjcmVhdGVfcmlnaHRfeV9heGlzOiBHcmFwaEhlbHBlck1ldGhvZHMuY3JlYXRlUmlnaHRZQXhpcyxcbiAgICAgICAgICAgIGNyZWF0ZV95X2F4aXM6IEdyYXBoSGVscGVyTWV0aG9kcy5jcmVhdGVMZWZ0WUF4aXMsXG4gICAgICAgICAgICB4X2F4aXM6IEdyYXBoSGVscGVyTWV0aG9kcy5tYWtlX3hfYXhpcyxcbiAgICAgICAgICAgIHlfYXhpczogR3JhcGhIZWxwZXJNZXRob2RzLm1ha2VfcmlnaHRfeV9heGlzLFxuICAgICAgICAgICAgaW5kaXZpZHVhbERhdGE6IG5ld1NldCxcbiAgICAgICAgICAgIGFzc2F5TWVhc3VyZW1lbnRzOiBiYXJBc3NheU9iaixcbiAgICAgICAgICAgIHdpZHRoOiA3NTAsXG4gICAgICAgICAgICBoZWlnaHQ6IDIyMFxuICAgICAgICB9O1xuXG4gICAgICAgIC8vcmVuZGVyIGRpZmZlcmVudCBncmFwaHNcbiAgICAgICAgY3JlYXRlTXVsdGlMaW5lR3JhcGgoZ3JhcGhTZXQsIEdyYXBoSGVscGVyTWV0aG9kcy5jcmVhdGVTdmcoc2VsZWN0b3JbMV0pKTtcbiAgICAgICAgY3JlYXRlR3JvdXBlZEJhckdyYXBoKGdyYXBoU2V0LCBHcmFwaEhlbHBlck1ldGhvZHMuY3JlYXRlU3ZnKHNlbGVjdG9yWzJdKSwgJ3gnKTtcbiAgICAgICAgY3JlYXRlR3JvdXBlZEJhckdyYXBoKGdyYXBoU2V0LCBHcmFwaEhlbHBlck1ldGhvZHMuY3JlYXRlU3ZnKHNlbGVjdG9yWzNdKSwgJ25hbWUnKTtcbiAgICAgICAgY3JlYXRlR3JvdXBlZEJhckdyYXBoKGdyYXBoU2V0LCBHcmFwaEhlbHBlck1ldGhvZHMuY3JlYXRlU3ZnKHNlbGVjdG9yWzRdKSwgJ21lYXN1cmVtZW50Jyk7XG5cbiAgICAgICAgLy9yZWN0YW5nbGUgc2VsZWN0b3JzIGZvciBlYWNoIGJhciBzdmcuXG4gICAgICAgIHZhciByZWN0QXNzYXlCYXIgPSBkMy5zZWxlY3RBbGwoJy5iYXJBc3NheSByZWN0JylbMF07XG4gICAgICAgIHZhciByZWN0TWVhc0JhciA9IGQzLnNlbGVjdEFsbCgnLmJhck1lYXN1cmVtZW50IHJlY3QnKVswXTtcbiAgICAgICAgdmFyIHJlY3RUaW1lQmFyID0gZDMuc2VsZWN0QWxsKCcuYmFyVGltZSByZWN0JylbMF07XG5cbiAgICAgICAgLy9tYWtlIHN1cmUgdGhlcmUgaXMgYSBtZXNzYWdlIHRvIGRpc3BsYXkgLSBwbGVhc2UgZmlsdGVyIC0gaWYgdGhlcmUgYXJlIG5vIGJhcnMgc2hvd2luZyBvbiBiYXIgZ3JhcGguIFxuICAgICAgICBpZiAoJChzZWxlY3RvclsyXSkuY3NzKCdkaXNwbGF5JykgPT09ICdibG9jaycpIHtcbiAgICAgICAgICAgICBTdHVkeUhlbHBlci5zdmdXaWR0aChzZWxlY3RvclsyXSwgcmVjdFRpbWVCYXIpO1xuICAgICAgICB9XG4gICAgICAgIGlmICgkKHNlbGVjdG9yWzNdKS5jc3MoJ2Rpc3BsYXknKSA9PT0gJ2Jsb2NrJykge1xuICAgICAgICAgICAgIFN0dWR5SGVscGVyLnN2Z1dpZHRoKHNlbGVjdG9yWzNdLCByZWN0QXNzYXlCYXIpO1xuICAgICAgICB9XG4gICAgICAgIGlmICgkKHNlbGVjdG9yWzRdKS5jc3MoJ2Rpc3BsYXknKSA9PT0gJ2Jsb2NrJykge1xuICAgICAgICAgICAgIFN0dWR5SGVscGVyLnN2Z1dpZHRoKHNlbGVjdG9yWzRdLCByZWN0TWVhc0Jhcik7XG4gICAgICAgIH1cblx0XHRpZiAoIW5ld1NldC5sYWJlbCkge1xuXHRcdFx0JCgnI2RlYnVnJykudGV4dCgnRmFpbGVkIHRvIGZldGNoIHNlcmllcy4nKTtcblx0XHRcdHJldHVybjtcblx0XHR9XG5cdH0sXG5cbn07Il19